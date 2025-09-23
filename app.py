
import os
import sys
import requests
import json
from flask import Flask, request, Response, jsonify, redirect
from datetime import datetime, timedelta
import re
import urllib.parse
import time
import base64
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
import googlemaps
import pytz 
from zoneinfo import ZoneInfo

# New Zealand timezone
NZ_TZ = pytz.timezone('Pacific/Auckland')

# Initialize client with your API key

# Try to import Google Cloud Speech, but make it optional with better error handling
GOOGLE_SPEECH_AVAILABLE = False
google_speech_client = None

try:
    from google.cloud import speech
    from google.oauth2 import service_account

    GOOGLE_SPEECH_AVAILABLE = True
    print("✅ Google Cloud Speech imported successfully")
except ImportError:
    print("⚠️ Google Cloud Speech not available - will use Twilio transcription only")
except Exception as e:
    print(
        f"⚠️ Google Cloud Speech import error: {e} - will use Twilio transcription only"
    )

app = Flask(__name__)
print("✅ Flask app created successfully")
# Initialize Google Maps client
gmaps = None
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
if GOOGLE_MAPS_API_KEY:
    try:
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        print("✅ Google Maps client initialized")
    except Exception as e:
        print(f"❌ Google Maps initialization failed: {e}")
else:
    print("⚠️ Google Maps API key not configured")

def validate_and_format_address(address, address_type="general"):
    """Validate and format address using Google Maps"""
    if not gmaps:
        return address
    
    try:
        # Add Wellington context if not present
        if "wellington" not in address.lower():
            search_address = f"{address}, Wellington, New Zealand"
        else:
            search_address = address
        
        # Use Google Geocoding
        results = gmaps.geocode(search_address, region="nz")

        print(f"🔍 Google Maps results: {results}")

        if(is_exact_address(results[0]) == False):
            return False
        
        if results:
            result = results[0]
            components = result['address_components']
            formatted_address = result['formatted_address']
            
            print(f"formatted address:::::: {formatted_address}")
            return formatted_address
        else:
            return address
            
    except Exception as e:
        print(f"❌ Google Maps error: {e}")
        return address

# Configuration - STEP 1: Environment Variables (with fallback to your key)
TAXICALLER_BASE_URL = "https://api.taxicaller.net/api/v1"
TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RENDER_ENDPOINT = os.getenv(
    "RENDER_ENDPOINT", "https://api-rc.taxicaller.net/api/v1/booker/order"
)

# Google Cloud and Twilio Configuration
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CLOUD_CREDENTIALS", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")

# JWT Token Cache (legacy - keeping for compatibility)
TAXICALLER_JWT_CACHE = {"token": None, "expires_at": 0}

# Session memory stores
user_sessions = {}
modification_bookings = {}
booking_storage = {}

print(
    f"🔑 TaxiCaller API Key: {'Configured (' + TAXICALLER_API_KEY[:8] + '...)' if TAXICALLER_API_KEY else 'Not configured'}"
)

# Database connection function
def get_db_connection():
    """Get PostgreSQL connection from DATABASE_URL"""
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL:
        # Render uses postgresql:// but psycopg2 needs postgres://
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        try:
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            return None
    return None


# Initialize database tables
def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            # Customers table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id SERIAL PRIMARY KEY,
                    phone_number VARCHAR(20) UNIQUE NOT NULL,
                    name VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_bookings INTEGER DEFAULT 0
                )
            """
            )

            # Bookings table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    customer_phone VARCHAR(20) NOT NULL,
                    customer_name VARCHAR(100),
                    pickup_location TEXT NOT NULL,
                    dropoff_location TEXT,
                    booking_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    scheduled_time TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'pending',
                    booking_reference VARCHAR(100),
                    raw_speech TEXT,
                    pickup_date VARCHAR(20),
                    order_id VARCHAR(20),
                    pickup_time VARCHAR(20),
                    created_via VARCHAR(20) DEFAULT 'ai_ivr'
                )
            """
            )

            # Conversation history table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    phone_number VARCHAR(20) NOT NULL,
                    message TEXT,
                    role VARCHAR(10),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.commit()
            cur.close()
            conn.close()
            print("✅ Database tables initialized")
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            if conn:
                conn.close()


# Run this once when app starts
init_db()


def init_google_speech():
    """Initialize Google Speech client with credentials"""
    if not GOOGLE_SPEECH_AVAILABLE:
        print("❌ Google Speech not available - using Twilio only")
        return None

    try:
        if GOOGLE_CREDENTIALS:
            creds_json = base64.b64decode(GOOGLE_CREDENTIALS).decode("utf-8")
            credentials = service_account.Credentials.from_service_account_info(
                json.loads(creds_json)
            )
            print("✅ Google Speech client initialized successfully")
            return speech.SpeechClient(credentials=credentials)
        print("⚠️ No Google credentials found")
        return None
    except Exception as e:
        print(f"❌ Failed to initialize Google Speech: {str(e)}")
        return None


# Initialize Google client if available
if GOOGLE_SPEECH_AVAILABLE:
    google_speech_client = init_google_speech()




def get_taxicaller_jwt():
    """Generate or retrieve a cached JWT token from TaxiCaller."""
    if (
        TAXICALLER_JWT_CACHE.get("token")
        and TAXICALLER_JWT_CACHE.get("expires_at", 0) > time.time()
    ):
        print("✅ Using cached JWT token")
        return TAXICALLER_JWT_CACHE["token"]

    print("🔄 Generating new JWT token...")
    try:
        jwt_endpoints = [
            "https://api-rc.taxicaller.net/api/v1/jwt/for-key",
        ]
        params = {"key": TAXICALLER_API_KEY, "sub": "*", "ttl": "900"}

        for jwt_url in jwt_endpoints:
            print(f"🔑 Trying JWT endpoint: {jwt_url}")
            try:
                response = requests.get(jwt_url, params=params, timeout=5)
                print(f"🌐 Status Code: {response.status_code}")
                print(f"📥 Raw Response: {response.text}")

                if response.status_code == 200:
                    jwt_token = response.text.strip()
                    TAXICALLER_JWT_CACHE["token"] = jwt_token
                    TAXICALLER_JWT_CACHE["expires_at"] = time.time() + 840
                    print(f"✅ JWT token generated successfully from {jwt_url}")
                    return jwt_token
                else:
                    print(f"❌ Failed JWT endpoint {jwt_url}: {response.status_code}")
            except Exception as e:
                print(f"❌ JWT endpoint {jwt_url} error: {str(e)}")
                continue

        print("❌ All JWT endpoints failed")
        return None
    except Exception as e:
        print(f"❌ Error generating JWT: {str(e)}")
        return None

# ✅ Call it
get_taxicaller_jwt()

def cancel_taxicaller_booking(order_id, original_booking=None):
    """Cancel booking using TaxiCaller API"""
    try:
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            return False

        try:
            token_data = json.loads(jwt_token)
            token = token_data['token']
        except (json.JSONDecodeError, KeyError):
            # If JWT token is not a JSON string or doesn't contain 'token' key
            token = jwt_token

        # Use the correct booker endpoint for cancellation
        cancel_url = f"https://api-rc.taxicaller.net/api/v1/booker/order/{order_id}/cancel"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "KiwiCabs-AI-IVR/2.1"
        }
        
        cancel_data = {"cancel_reason": "Customer requested modification"}
        
        print(f"🛠️ DEBUG: Sending TaxiCaller cancel request to: {cancel_url}")
        print(f"🛠️ DEBUG: Cancel headers: {headers}")
        print(f"🛠️ DEBUG: Cancel data: {cancel_data}")
        
        response = requests.post(cancel_url, headers=headers, json=cancel_data, timeout=10)
        
        print(f"🛠️ DEBUG: Cancel response status: {response.status_code}")
        print(f"🛠️ DEBUG: Cancel response body: {response.text}")
        
        if response.status_code in [200, 202, 204]:
            print(f"✅ BOOKING {order_id} CANCELLED SUCCESSFULLY")
            return True
        else:
            print(f"❌ CANCEL FAILED: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ CANCEL ERROR: {str(e)}")
        return False

def handle_taxicaller_cancel_response(response):
    """
    Handles the TaxiCaller cancellation API response,
    returning a tuple: (success: bool, response_xml: str)
    """
    if response.status_code == 200:
        print("✅ Cancellation successful!")
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! I've cancelled your booking. Thanks for letting us know!
    </Say>
    <Hangup/>
</Response>
"""
        return True, response_xml

    elif response.status_code == 404:
        print("❌ Booking not found for cancellation.")
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I couldn't find your booking to cancel.
    </Say>
    <Hangup/>
</Response>
"""
        return False, response_xml

    elif response.status_code == 403:
        print("ℹ️ Booking already cancelled or not allowed.")
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Your booking appears to be already cancelled or cannot be cancelled.
    </Say>
    <Hangup/>
</Response>
"""
        return False, response_xml

    else:
        print("❌ Cancellation failed with unexpected error.")
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, something went wrong while processing your request.
    </Say>
    <Hangup/>
</Response>
"""
        return False, response_xml

def edit_taxicaller_booking(order_id, new_time_str, booking_data=None):
    """Edit existing booking using TaxiCaller EDIT endpoint (recommended approach)"""
    if not order_id or order_id == "None":
        print("❌ No valid order_id provided to edit_taxicaller_booking")
        return False

    try:
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            return False

        try:
            token_data = json.loads(jwt_token)
            token = token_data['token']
        except (json.JSONDecodeError, KeyError):
            # If JWT token is not a JSON string or doesn't contain 'token' key
            token = jwt_token

        edit_url = f"https://api-rc.taxicaller.net/api/v1/booker/order/{order_id}"

        # Convert new time to Unix timestamp
        new_time_unix = int(datetime.strptime(new_time_str, "%Y-%m-%d %H:%M:%S").timestamp())

        # Prepare payload for editing booking
        payload = {
            "route": {
                "nodes": [
                    {
                        "times": {
                            "arrive": {
                                "target": new_time_unix
                            }
                        }
                    }
                ]
            }
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        print(f"✏️ EDITING BOOKING: {order_id}")
        response = requests.put(edit_url, headers=headers, json=payload, timeout=10)

        print(f"📥 EDIT RESPONSE: {response.status_code} - {response.text}")

        if response.status_code in [200, 204]:
            print(f"✅ BOOKING UPDATED: {order_id}")
            return True
        else:
            print(f"❌ EDIT FAILED: {response.text}")
            return False

    except Exception as e:
        print(f"❌ EDIT ERROR: {e}")
        return False

def is_exact_address(result):
    components = result.get("address_components", [])
    types = [t for c in components for t in c["types"]]

    # Exact street address: must have street number + route
    if "street_number" in types and "route" in types:
        return True

    # POI / landmark: establishment, point_of_interest, etc.
    if any(t in types for t in ["establishment", "point_of_interest", "transit_station"]):
        return True
    
    return False

def parse_address(address: str):
    import openai
    openai.api_key = OPENAI_API_KEY
    
    prompt = f"""
You are an expert Wellington, New Zealand taxi dispatcher AI.
Your job is to clean, correct, and standardize customer-provided addresses.

RULES:
- Always assume the address is in Wellington, New Zealand unless explicitly told otherwise.
- If the suburb/street is misspelled or unclear, correct it to the closest valid Wellington suburb/street/landmark.
  Example: "Belrose" → "Melrose", "Mirmar" → "Miramar".
- Output two strings only:
  1. "clean_address": just house/flat number, street, suburb (no postcode, city, country).
  2. "full_address": corrected, complete official format including postcode, Wellington, New Zealand.
- Recognize flats/apartments:
  Example: "flat2 slash 55 melrose road melrose" → clean_address: "2/55 Melrose Road, Melrose".
- Recognize landmarks/POIs:
  Example: "Wellington Airport" → clean_address: "Wellington Airport, Rongotai".
  Example: "Te Papa" → clean_address: "Te Papa Museum, Wellington Central".

EXAMPLES:
Input: "63 hobart st miramar"
→ clean_address: "63 Hobart Street, Miramar"
→ full_address: "63 Hobart Street, Miramar, Wellington 6022, New Zealand"

Input: "flat2 slash 55 belrose road melrose"
→ clean_address: "2/55 Melrose Road, Melrose"
→ full_address: "2/55 Melrose Road, Melrose, Wellington 6023, New Zealand"

Input: "wellington airport"
→ clean_address: "Wellington Airport, Rongotai"
→ full_address: "Wellington International Airport, Stewart Duff Drive, Rongotai, Wellington 6022, New Zealand"

CUSTOMER SAID: "{address}"

Respond ONLY with the two strings in this format:
clean_address: ...
full_address: ...
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an NZ address parser and formatter."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    output = response.choices[0].message.content.strip()
    print(f"gpt result address for output: {output}")

    # Split into two variables
    clean_address, full_address = None, None
    match = re.search(r'clean_address:\s*"(.*?)"', output)
    clean_address = match.group(1) if match else None

    match = re.search(r'full_address:\s*"(.*?)"', output)
    full_address = match.group(1) if match else None

    clean_address = normalize_unit_slash_address(clean_address)
    return clean_address, full_address

def normalize_unit_slash_address(addr: str, lowercase_unit: bool = True) -> str:
    """
    Convert addresses of the forms:
      "2/55 Melrose Road, Melrose" -> "unit 2 at 55 Melrose Road, Melrose"
      "Flat 2, 55 Melrose Rd"      -> "unit 2 at 55 Melrose Rd"
      "Unit 2/55 Melrose Rd"      -> "unit 2 at 55 Melrose Rd"
      "1a/55 Melrose Road"        -> "unit 1a at 55 Melrose Road"

    If the address already appears to be in the target form ("unit X at ..."),
    it is returned unchanged.

    Args:
      addr: input address string
      lowercase_unit: if True produce "unit ...", else "Unit ..."

    Returns:
      normalized address string
    """
    if not addr or not isinstance(addr, str):
        return addr

    target_unit_word = "unit" if lowercase_unit else "Unit"

    # If already normalized, return as-is (case-insensitive check)
    if re.search(rf'\b{target_unit_word}\s+\w+\s+at\b', addr, flags=re.IGNORECASE):
        return addr

    s = addr.strip()

    # Patterns to match unit/house-number styles at start or after punctuation
    patterns = [
        # e.g. "2/55 Rest..." or "1a/55 Rest" or "2\55 Rest" or "2-55 Rest"
        r'(?P<prefix>^|\s|,)(?P<unit>[0-9]+[A-Za-z]?)[\s]*[\/\\\-][\s]*(?P<number>\d+)\b(?P<rest>.*)',
        # e.g. "Flat 2, 55 Rest" or "flat 2 55 Rest" or "Unit 2, 55 Rest"
        r'(?P<prefix>^|\s|,)(?P<label>Flat|flat|FLAT|Unit|unit)[\s\.]*?(?P<unit>[0-9]+[A-Za-z]?)[\s,]+(?P<number>\d+)\b(?P<rest>.*)'
    ]

    for pat in patterns:
        def repl(m):
            # m.group('prefix') preserves leading whitespace/comma if present
            prefix = m.group('prefix') or ''
            unit = m.group('unit')
            number = m.group('number')
            rest = m.group('rest') or ''
            # strip leading spaces from rest to avoid double spaces
            rest = rest.lstrip()
            return f"{prefix}{target_unit_word} {unit} at {number} {rest}".rstrip()

        new_s, count = re.subn(pat, repl, s, count=1)
        if count:
            # clean extra spaces/commas
            new_s = re.sub(r'\s+,', ',', new_s)
            new_s = re.sub(r'\s{2,}', ' ', new_s).strip()
            return new_s

    # If nothing matched, just return original (or optionally apply other normalizations)
    return s

def clean_address_for_speech(address):
    """Clean address for AI speech - remove postcodes, Wellington, New Zealand"""
    if not address:
        return address

    import re

    cleaned = normalize_unit_slash_address(address)
    # Remove postcodes (4-digit numbers)
    cleaned = re.sub(r',?\s*\d{4}\s*,?', '', cleaned)
    cleaned = cleaned.replace("/", "")

    # Remove "Wellington" and "New Zealand"
    cleaned = cleaned.replace(", Wellington", "").replace(" Wellington", "")
    cleaned = cleaned.replace(", New Zealand", "").replace(" New Zealand", "")

    # Clean up extra commas and spaces
    cleaned = re.sub(r',\s*,', ',', cleaned)
    cleaned = cleaned.strip(', ')

    return cleaned

def format_time_for_speech(time_str):
    """Convert 24-hour time format (15:00) to 12-hour format with AM/PM (3 PM) for speech"""
    if not time_str or time_str.upper() in ["ASAP", "NOW", "IMMEDIATELY"]:
        return time_str

    try:
        # Handle different time formats
        if "AM" in time_str.upper() or "PM" in time_str.upper() or "A.M." in time_str.upper() or "P.M." in time_str.upper():
            # Already in 12-hour format, just clean it up
            cleaned = time_str.replace("a.m.", "AM").replace("p.m.", "PM").replace("A.M.", "AM").replace("P.M.", "PM")
            return cleaned.replace("a.M.", "AM").replace("p.M.", "PM")

        # Handle 24-hour format (15:00, 15:30, etc.)
        if ":" in time_str:
            try:
                # Parse 24-hour format
                time_obj = datetime.strptime(time_str.strip(), "%H:%M").time()
                # Convert to 12-hour format
                return time_obj.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ')
            except ValueError:
                pass

        # Handle single digit hours (15, 9, etc.)
        if time_str.isdigit():
            hour = int(time_str)
            if hour == 0:
                return "12 AM"
            elif hour < 12:
                return f"{hour} AM"
            elif hour == 12:
                return "12 PM"
            else:
                return f"{hour - 12} PM"

        # If we can't parse it, return as is
        return time_str

    except Exception as e:
        print(f"⚠️ Error formatting time for speech: {e}")
        return time_str

def resolve_wellington_poi_to_address(place_name):
    """Convert Wellington POI names to exact addresses using Google Maps"""
    if not gmaps:
        return place_name
    
    try:
        print(f"🔍 Resolving Wellington POI: {place_name}")
        
        # Try multiple search strategies
        # search_queries = [
        #     f"{place_name}, Wellington, New Zealand",
        #     f"{place_name}, Lower Hutt, New Zealand", 
        #     f"{place_name}, Upper Hutt, New Zealand",
        #     f"{place_name}, Porirua, New Zealand"
        # ]
        
        # for query in search_queries:
        #     try:
        #         # First try Places API for businesses/landmarks
        #         places_result = gmaps.places(
        #             query=query,
        #             radius=50000,  # 50km radius
        #             location=(-41.2924, 174.7787)  # Wellington coordinates
        #         )
                
        #         if places_result.get('results'):
        #             best_place = places_result['results'][0]
        #             place_address = best_place.get('formatted_address', '')
        #             place_actual_name = best_place.get('name', place_name)
                    
        #             print(f"✅ FOUND POI: {place_actual_name} → {place_address}")
        #             clean_address = clean_address_for_speech(place_address)
        #             return {
        #                 "full_address": place_address,
        #                 "poi_name": place_actual_name,
        #                 "clean_address": clean_address,
        #                 "speech": f"{place_actual_name} at {clean_address}"
        #             }
        #     except Exception as e:
        #         print(f"⚠️ Places search failed for {query}: {e}")
        #         continue
        
        # Fallback to geocoding
        if "wellington" not in place_name.lower():
            search_address = f"{place_name}, Wellington, New Zealand"
        else:
            search_address = place_name

        geocode_result = gmaps.geocode(search_address, region="nz")

        print(f"geocode result:{geocode_result}")

        if(is_exact_address(geocode_result[0]) == False):
            return False

        if geocode_result:
            address = geocode_result[0]['formatted_address']
            print(f"✅ GEOCODED: {place_name} → {address}")
            clean_address = clean_address_for_speech(address)
            return {
                "full_address": address,
                "poi_name": place_name,
                "clean_address": clean_address,
                "speech": f"{place_name} at {clean_address}"
            }
            
        print(f"❌ Could not resolve: {place_name}")
        return {
            "full_address": place_name,
            "poi_name": place_name,
            "clean_address": place_name,
            "speech": place_name
        }
        
    except Exception as e:
        print(f"❌ POI resolution error: {e}")
        return {
            "full_address": place_name,
            "poi_name": place_name,
            "clean_address": place_name,
            "speech": place_name
        }

def extract_time_with_ai(speech_text):
    """Extract time information from speech using the same logic as booking creation"""
    try:
        # Use the same time processing logic as in the booking creation flow
        time_text = speech_text.lower().strip()
        result = {}

        # Check for immediate booking (same as booking creation)
        immediate_keywords = ["now", "right now", "immediately", "asap", "as soon as possible", "straight away"]
        if any(keyword in time_text for keyword in immediate_keywords):
            result["pickup_time"] = "ASAP"
            result["pickup_date"] = datetime.now(NZ_TZ).strftime("%d/%m/%Y")
            return result
        else:
            # Parse time using existing logic (same as booking creation)
            print(f"📝 Time modification - parsing speech: {speech_text}")
            parsed_booking = parse_booking_speech(speech_text)
            print(f"📝 Time modification - parsed result: {parsed_booking}")

            if parsed_booking and parsed_booking.get("pickup_time"):
                result["pickup_time"] = parsed_booking["pickup_time"]

                if parsed_booking.get("pickup_date"):
                    result["pickup_date"] = parsed_booking["pickup_date"]
                else:
                    # Default to today if no date specified (same as booking creation)
                    result["pickup_date"] = datetime.now(NZ_TZ).strftime("%d/%m/%Y")

                # Validate that the time is not in the past (same as booking creation)
                datetime_str = f"{result['pickup_date']} {result['pickup_time']}"
                booked_time = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
                booked_time = booked_time.replace(tzinfo=ZoneInfo("Pacific/Auckland"))

                if booked_time < datetime.now(NZ_TZ):
                    print(f"⚠️ Time modification - time is in the past: {booked_time}")
                    return None  # Time is in the past

                return result
            else:
                return None

    except Exception as e:
        print(f"❌ Error extracting time with AI: {e}")
        return None

def extract_modification_intent_with_ai(speech_text, current_booking):
    """Use OpenAI to understand modification requests naturally with Wellington POI knowledge"""
    
    if not OPENAI_API_KEY:
        print("⚠️ No OpenAI API key - falling back to basic parsing")
        return None
    
    try:
        prompt = f"""You are a Wellington, New Zealand taxi dispatcher AI with comprehensive local knowledge.

CURRENT BOOKING:
- Pickup: {current_booking.get('pickup_address', 'Unknown')}
- Destination: {current_booking.get('destination', 'Unknown')}
- Time: {current_booking.get('pickup_time', 'Unknown')}

CUSTOMER SAID: "{speech_text}"

Extract what they want to change. Use your knowledge of Wellington landmarks, businesses, hospitals, hotels, restaurants, attractions, and POIs.

WELLINGTON POI EXAMPLES:
- Hospitals: "Hutt Hospital", "Wellington Hospital", "Bowen Hospital", "Kenepuru Hospital"
- Hotels: "James Cook Hotel", "InterContinental Wellington", "Bolton Hotel"
- Attractions: "Te Papa", "Weta Cave", "Wellington Zoo", "Cable Car", "Sky Stadium"
- Shopping: "Westfield Queensgate", "Lambton Quay", "Cuba Mall"
- Transport: "Wellington Airport", "Wellington Station", "Railway Station"
- Areas: "Lower Hutt", "Upper Hutt", "Miramar", "Kelburn", "Newtown"

What does the customer want to change? Respond ONLY with JSON:
{{"intent": "change_pickup|change_destination|change_time|cancel|no_change", "new_value": "exact place name or time", "confidence": 0.95}}

Examples:
"change destination to Hutt Hospital" → {{"intent": "change_destination", "new_value": "Hutt Hospital", "confidence": 0.95}}
"go to Weta Cave instead" → {{"intent": "change_destination", "new_value": "Weta Cave", "confidence": 0.92}}
"pick me up from James Cook Hotel" → {{"intent": "change_pickup", "new_value": "James Cook Hotel", "confidence": 0.90}}"""

        import openai
        openai.api_key = OPENAI_API_KEY
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1
        )
        
        ai_response = response.choices[0].message.content.strip()
        print(f"🤖 AI PARSED: {ai_response}")
        
        import json
        return json.loads(ai_response)
        
    except Exception as e:
        print(f"❌ AI parsing error: {e}")
        return None


def send_booking_to_taxicaller(booking_data, caller_number):
    """Send booking to TaxiCaller API using the correct v1 endpoint"""
    try:
        # Get environment variables
        TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY")
        COMPANY_ID = os.getenv("COMPANY_ID", "")
        USER_ID = os.getenv("USER_ID", "")  # Optional

        if not TAXICALLER_API_KEY:
            print("❌ No TaxiCaller API key available")
            return False, None

        # 🔑 Generate the JWT token
        jwt_token = get_taxicaller_jwt()

        print(f"🔐 Using TaxiCaller API Key: {TAXICALLER_API_KEY[:8]}...")
        print(f"🔑 JWT Token: {jwt_token[:20]}..." if jwt_token else "🔑 No JWT Token available")

        if COMPANY_ID:
            print(f"🏢 Company ID: {COMPANY_ID}")

        # Format time to ISO format with NZ timezone as per your instructions
        is_immediate = booking_data.get("pickup_time", "").upper() in [
            "ASAP",
            "NOW",
            "IMMEDIATELY",
        ]

        if is_immediate:
            # For immediate bookings, use current time + 5 minutes
            pickup_datetime = datetime.now(NZ_TZ) + timedelta(minutes=5)
        else:
            # Parse date and time from booking data
            try:
                if booking_data.get("pickup_date"):
                    # Parse date in DD/MM/YYYY format
                    date_parts = booking_data["pickup_date"].split("/")
                    year = int(date_parts[2])
                    month = int(date_parts[1])
                    day = int(date_parts[0])
                else:
                    # Default to today
                    today = datetime.now(NZ_TZ)
                    year, month, day = today.year, today.month, today.day

                # Parse time
                time_str = booking_data.get("pickup_time", "9:00 AM")
                if "AM" in time_str or "PM" in time_str:
                    pickup_time = datetime.strptime(time_str, "%I:%M %p").time()
                else:
                    pickup_time = datetime.strptime(time_str, "%H:%M").time()

                pickup_datetime = datetime.combine(
                    datetime(year, month, day).date(), pickup_time
                )
            except Exception as e:
                print(f"❌ Error parsing date/time: {e}, using current time + 1 hour")
                pickup_datetime = datetime.now(NZ_TZ) + timedelta(hours=1)

        # Format to ISO format WITHOUT timezone as per guide
        pickup_time_iso = pickup_datetime.strftime("%Y-%m-%dT%H:%M:%S+12:00")

        # Get coordinates for pickup and destination using Google Maps
        pickup_coords = [0, 0]  # Default fallback
        dropoff_coords = [0, 0]  # Default fallback
        
        if gmaps:
            try:
                # Get pickup coordinates
                pickup_geocode = gmaps.geocode(booking_data.get('pickup_address', '') + ", Wellington, New Zealand", region="nz")
                if pickup_geocode:
                    pickup_lat = pickup_geocode[0]['geometry']['location']['lat']
                    pickup_lng = pickup_geocode[0]['geometry']['location']['lng']
                    pickup_coords = [int(pickup_lng * 1000000), int(pickup_lat * 1000000)]
                
                # Get dropoff coordinates  
                dropoff_geocode = gmaps.geocode(booking_data.get('destination', '') + ", Wellington, New Zealand", region="nz")
                if dropoff_geocode:
                    dropoff_lat = dropoff_geocode[0]['geometry']['location']['lat']
                    dropoff_lng = dropoff_geocode[0]['geometry']['location']['lng']
                    dropoff_coords = [int(dropoff_lng * 1000000), int(dropoff_lat * 1000000)]
            except Exception as e:
                print(f"⚠️ Geocoding error: {e}")

        # Convert pickup time to Unix timestamp
        pickup_timestamp = 0  # Default for ASAP
        if not is_immediate:
            pickup_timestamp = int(NZ_TZ.localize(pickup_datetime).timestamp())

        # Create TaxiCaller compliant payload
        # Convert only NZ international numbers to local format
        nz_local_phone = caller_number
        if caller_number.startswith("+64"):
            nz_local_phone = "0" + caller_number[3:]  # +64220881234 → 0220881234
        elif caller_number.startswith("64") and len(caller_number) == 11:  # Ensure it's NZ format
            nz_local_phone = "0" + caller_number[2:]  # 64220881234 → 0220881234
        booking_payload = {
            "order": {
                "company_id": 8257,
                "provider_id": 0,
                "items": [
                    {
                        "@type": "passengers",
                        "seq": 0,
                        "passenger": {
                            "name": booking_data.get('name', 'Customer'),
                            "email": "customer@kiwicabs.co.nz",
                            "phone": nz_local_phone
                        },
                        "client_id": 0,
                        "account": {"id": 0},
                        "require": {"seats": 1, "wc": 0, "bags": 1},
                        "pay_info": [{"@t": 0, "data": None}]
                    }
                ],
                "route": {
                    "meta": {"est_dur": "600", "dist": "5000"},
                    "nodes": [
                        {
                            "actions": [{"@type": "client_action", "item_seq": 0, "action": "in"}],
                            "location": {
                                "name": booking_data.get('pickup_address', ''),
                                "coords": pickup_coords
                            },
                            "times": {"arrive": {"target": pickup_timestamp}},
                            "info": {"all": booking_data.get("driver_instructions", "")},
                            "seq": 0
                        },
                        {
                            "actions": [{"@type": "client_action", "item_seq": 0, "action": "out"}],
                            "location": {
                                "name": booking_data.get('destination', ''),
                                "coords": dropoff_coords
                            },
                            "seq": 1
                        }
                    ],
                    "legs": [
                        {
                            "pts": pickup_coords + dropoff_coords,
                            "meta": {"dist": "5000", "est_dur": "600"},
                            "from_seq": 0,
                            "to_seq": 1
                        }
                    ]
                }
            }
        }

        # Define endpoints and headers for the loop
        try:
            # Get token from JWT response
            token = ""
            if jwt_token:
                try:
                    token_data = json.loads(jwt_token)
                    token = token_data['token']
                except (json.JSONDecodeError, KeyError):
                    # If JWT token is not a JSON string or doesn't contain 'token' key
                    token = jwt_token
                
            possible_endpoints = [
                "https://api-rc.taxicaller.net/api/v1/booker/order",  # Fallback
            ]
            headers_options = [
                {
                    "Content-Type": "application/json",
                    "User-Agent": "KiwiCabs-AI-IVR/2.1"
                }
            ]
            
            if token:
                headers_options.append({   
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "KiwiCabs-AI-IVR/2.1"
                })
            
            print(f"📤 SENDING TO TAXICALLER V2:")
            print(f"   API Key: {TAXICALLER_API_KEY[:8]}...")
            print(f"   Customer: {booking_payload['order']['items'][0]['passenger']['name']}")
            print(f"   Phone: {booking_payload['order']['items'][0]['passenger']['phone']}")
            print(f"   Pickup: {booking_payload['order']['route']['nodes'][0]['location']['name']}")
            print(f"   Dropoff: {booking_payload['order']['route']['nodes'][1]['location']['name']}")
            print(f"   Time: {booking_payload['order']['route']['nodes'][0]['times']['arrive']['target']}")
            
            # Try multiple TaxiCaller endpoints
            for endpoint in possible_endpoints:
                for headers in headers_options:
                    try:
                        print(f"📤 TRYING ENDPOINT: {endpoint}")
                        print(f"📤 TRYING HEADERS: {headers}")
                        
                        response = requests.post(
                            endpoint,
                            json=booking_payload,
                            timeout=3,  # Quick timeout - don't make customer wait
                            headers=headers,
                        )
                        
                        print(f"📥 TAXICALLER RESPONSE: {response.status_code}")
                        print(f"📥 RESPONSE BODY: {response.text}")
                        
                        # Log the API response and handle errors
                        if response.status_code in [200, 201]:
                            try:
                                response_data = response.json()
                                order_id = response_data.get("order", {}).get("order_id", "Unknown")
                                booking_id = response_data.get("bookingId") or order_id
                                
                                # STORE ORDER ID for future cancellation/editing
                                booking_data["taxicaller_order_id"] = order_id 
                                
                                # Ensure booking_storage exists for this caller
                                if caller_number not in booking_storage:
                                    booking_storage[caller_number] = {}
                                
                                # Update the stored booking with order ID
                                booking_storage[caller_number].update(booking_data)
                                booking_storage[caller_number]["taxicaller_order_id"] = order_id

                                # Update database with the new order ID
                                try:
                                    update_booking_to_db(caller_number, booking_storage[caller_number])
                                    print(f"✅ DATABASE UPDATED with new order ID: {order_id}")
                                except Exception as db_error:
                                    print(f"❌ DATABASE UPDATE FAILED: {db_error}")

                                print(f"✅ TAXICALLER BOOKING CREATED: {booking_id} (Order ID: {order_id})")
                                print(f"🔗 ORDER ID STORED in booking_storage[{caller_number}]")
                                return True, response_data
                            except:
                                print(f"✅ TAXICALLER BOOKING CREATED (no JSON response)")
                                return True, {"status": "created", "response": response.text}
                        elif response.status_code == 401:
                            print(f"🔑 AUTHENTICATION ERROR - API key may be invalid or need different format")
                            continue  # Try next header format
                        elif response.status_code == 403:
                            print(f"🚫 FORBIDDEN - API key may not have booking permissions")
                            continue  # Try next endpoint/header
                        else:
                            print(f"❌ ENDPOINT {endpoint} FAILED: {response.status_code}")
                            continue  # Try next endpoint
                            
                    except requests.exceptions.ConnectionError as e:
                        print(f"❌ CONNECTION ERROR for {endpoint}: Domain doesn't exist")
                        break  # Try next endpoint (no point trying other headers)
                    except Exception as e:
                        print(f"❌ ERROR for {endpoint}: {str(e)}")
                        continue  # Try next header/endpoint
            
            # If all endpoints failed
            print(f"❌ ALL TAXICALLER ENDPOINTS FAILED")
            return False, None

        except Exception as e:
            print("⚠️ Error while defining endpoints or headers:", e)
            try:
                print(f"📤 SENDING TO TAXICALLER V2:")
                print(f"   URL: https://api-rc.taxicaller.net/api/v1/booker/order")
                print(f"   API Key: {TAXICALLER_API_KEY[:8]}..." if TAXICALLER_API_KEY else "No API key")
                # Safely print booking information if available
                if 'booking_payload' in locals():
                    payload = booking_payload
                    try:
                        print(f"   Customer: {payload['order']['items'][0]['passenger']['name']}")
                        print(f"   Phone: {payload['order']['items'][0]['passenger']['phone']}")
                        print(f"   Pickup: {payload['order']['route']['nodes'][0]['location']['name']}")
                        print(f"   Dropoff: {payload['order']['route']['nodes'][1]['location']['name']}")
                        print(f"   Time: {payload['order']['route']['nodes'][0]['times']['arrive']['target']}")
                    except (KeyError, IndexError) as payload_error:
                        print(f"   Error accessing payload fields: {payload_error}")
                else:
                    print("   Booking payload not available")
            except Exception as debug_err:
                print("⚠️ Debug info not available:", debug_err)
            return False, None

    except Exception as e:
        print(f"❌ TAXICALLER API ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None



def update_booking_to_db(caller_number, updated_booking):
    #update the database with new booking details
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE bookings
                SET
                    customer_name = %s,
                    pickup_location = %s,
                    dropoff_location = %s,
                    pickup_date = %s,
                    pickup_time = %s,
                    order_id = %s
                WHERE customer_phone = %s
                """,
                (
                    updated_booking.get("name", ""),
                    updated_booking.get("pickup_address", ""),
                    updated_booking.get("destination", ""),
                    updated_booking.get("pickup_date", ""),
                    updated_booking.get("pickup_time", ""),
                    updated_booking.get("taxicaller_order_id", ""),
                    caller_number,  # this is used in the WHERE clause
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ DATABASE UPDATED: order_id={updated_booking.get('taxicaller_order_id', 'N/A')}")
        except Exception as e:
            print(f"❌ Error updating booking in database: {e}")
            if conn:
                conn.close()

# Background processing functions for booking modifications
def background_destination_modification(caller_number, updated_booking, original_booking=None):
    """Background process to modify destination"""
    try:
        print("🔄 BACKGROUND: Starting destination modification...")

        # Get order ID from storage
        stored_booking = booking_storage.get(caller_number, {})
        old_order_id = stored_booking.get("taxicaller_order_id")

        if not old_order_id and original_booking:
            old_order_id = original_booking.get("taxicaller_order_id")

        print(f"🛠️ DEBUG: old_order_id for destination change: {old_order_id}")
                    
        if old_order_id:
            # Try to cancel the old booking
            print(f"✅ ATTEMPTING TO CANCEL OLD BOOKING: {old_order_id}")
            cancel_success = cancel_taxicaller_booking(old_order_id)
            print(f"🛠️ DEBUG: Cancel result: {cancel_success}")

            # Proceed with new booking regardless of cancellation result
            # (cancellation might fail if booking is already dispatched, etc.)
            if cancel_success:
                print("✅ OLD BOOKING CANCELLED")
            else:
                print("⚠️ CANCEL FAILED - proceeding with new booking anyway")
            
            time.sleep(2)  # Adding delay after cancellation attempt

            # Create new booking with new destination
            updated_booking["modified_at"] = datetime.now(NZ_TZ).isoformat()
            updated_booking["ai_modified"] = True
            print(f"🛠️ DEBUG: About to create new booking: {updated_booking}")
            
            success, response = send_booking_to_api(updated_booking, caller_number)
            print(f"🛠️ DEBUG: New booking result: success={success}, response={response}")

            if success:
                print("✅ NEW BOOKING CREATED with new destination")
                # Store new order ID for future modifications
                if response and "orderId" in response:
                    updated_booking["taxicaller_order_id"] = response["orderId"]
                    booking_storage[caller_number] = updated_booking
                    print(f"✅ NEW ORDER ID STORED: {response['orderId']}")
                
                # Update database with new destination and order ID
                try:
                    update_booking_to_db(caller_number, updated_booking)
                    print("✅ DATABASE UPDATED with new destination")
                    print(f"🎯 DESTINATION MODIFICATION COMPLETE:")
                    print(f"   📞 Customer: {caller_number}")
                    print(f"   🆔 Old Order ID: {old_order_id}")
                    print(f"   🆔 New Order ID: {updated_booking.get('taxicaller_order_id', 'N/A')}")
                    print(f"   📍 New Destination: {updated_booking.get('destination', 'N/A')}")
                    print(f"   ✅ TaxiCaller: Updated")
                    print(f"   ✅ Database: Updated")
                    print(f"   ✅ Memory: Updated")
                except Exception as db_error:
                    print(f"❌ DATABASE UPDATE FAILED: {db_error}")
                    print(f"⚠️ DESTINATION MODIFICATION PARTIAL:")
                    print(f"   📞 Customer: {caller_number}")
                    print(f"   🆔 Old Order ID: {old_order_id}")
                    print(f"   🆔 New Order ID: {updated_booking.get('taxicaller_order_id', 'N/A')}")
                    print(f"   📍 New Destination: {updated_booking.get('destination', 'N/A')}")
                    print(f"   ✅ TaxiCaller: Updated")
                    print(f"   ❌ Database: Failed")
                    print(f"   ✅ Memory: Updated")
            else:
                print("❌ NEW BOOKING FAILED")
                # Still update database with destination change even if TaxiCaller fails
                try:
                    update_booking_to_db(caller_number, updated_booking)
                    print("✅ DATABASE UPDATED (TaxiCaller failed but DB updated)")
                except Exception as db_error:
                    print(f"❌ DATABASE UPDATE ALSO FAILED: {db_error}")
        else:
            print("❌ NO ORDER ID FOUND for destination change")
            # Still update database with destination change
            try:
                update_booking_to_db(caller_number, updated_booking)
                print("✅ DATABASE UPDATED (no TaxiCaller order to modify)")
            except Exception as db_error:
                print(f"❌ DATABASE UPDATE FAILED: {db_error}")

        print("✅ BACKGROUND: Destination modification completed")
    except Exception as e:
        print(f"❌ BACKGROUND: Destination modification error: {str(e)}")
        # Fallback: at least try to update the database
        try:
            update_booking_to_db(caller_number, updated_booking)
            print("✅ FALLBACK: Database updated despite error")
        except Exception as db_error:
            print(f"❌ FALLBACK: Database update also failed: {db_error}")




def background_pickup_modification(caller_number, updated_booking, original_booking=None):
    """Background process to modify pickup"""
    try:
        print("🔄 BACKGROUND: Starting pickup modification...")

        # Get order ID from storage
        stored_booking = booking_storage.get(caller_number, {})
        old_order_id = stored_booking.get("taxicaller_order_id")

        if not old_order_id and original_booking:
            old_order_id = original_booking.get("taxicaller_order_id")

        print(f"🛠️ DEBUG: old_order_id for pickup change: {old_order_id}")

        if old_order_id:
            # Try to cancel the old booking
            print(f"✅ ATTEMPTING TO CANCEL OLD BOOKING: {old_order_id}")
            cancel_success = cancel_taxicaller_booking(old_order_id)
            print(f"🛠️ DEBUG: Cancel result: {cancel_success}")

            # Proceed with new booking regardless of cancellation result
            if cancel_success:
                print("✅ OLD BOOKING CANCELLED")
            else:
                print("⚠️ CANCEL FAILED - proceeding with new booking anyway")

            time.sleep(2)  # Adding delay after cancellation attempt

            # Create new booking with new pickup
            updated_booking["modified_at"] = datetime.now(NZ_TZ).isoformat()
            updated_booking["ai_modified"] = True
            booking_storage[caller_number] = updated_booking
            print(f"🛠️ DEBUG: About to create new booking: {updated_booking}")
            
            success, response = send_booking_to_api(updated_booking, caller_number)
            print(f"🛠️ DEBUG: New booking result: success={success}, response={response}")

            if success:
                print("✅ NEW BOOKING CREATED with new pickup")
                # Store new order ID for future modifications
                if response and "orderId" in response:
                    updated_booking["taxicaller_order_id"] = response["orderId"]
                    booking_storage[caller_number] = updated_booking
                    print(f"✅ NEW ORDER ID STORED: {response['orderId']}")
                
                # Update database with new pickup location and order ID
                try:
                    update_booking_to_db(caller_number, updated_booking)
                    print("✅ DATABASE UPDATED with new pickup")
                except Exception as db_error:
                    print(f"❌ DATABASE UPDATE FAILED: {db_error}")
            else:
                print("❌ NEW BOOKING FAILED")
                # Still update database with pickup change even if TaxiCaller fails
                try:
                    update_booking_to_db(caller_number, updated_booking)
                    print("✅ DATABASE UPDATED (TaxiCaller failed but DB updated)")
                except Exception as db_error:
                    print(f"❌ DATABASE UPDATE ALSO FAILED: {db_error}")
        else:
            print("❌ NO ORDER ID FOUND for pickup change")
            # Still update database with pickup change
            try:
                update_booking_to_db(caller_number, updated_booking)
                print("✅ DATABASE UPDATED (no TaxiCaller order to modify)")
            except Exception as db_error:
                print(f"❌ DATABASE UPDATE FAILED: {db_error}")

        print("✅ BACKGROUND: Pickup modification completed")
    except Exception as e:
        print(f"❌ BACKGROUND: Pickup modification error: {str(e)}")
        # Fallback: at least try to update the database
        try:
            update_booking_to_db(caller_number, updated_booking)
            print("✅ FALLBACK: Database updated despite error")
        except Exception as db_error:
            print(f"❌ FALLBACK: Database update also failed: {db_error}")

def background_time_modification(caller_number, updated_booking, original_booking=None, time_string=None):
    """Background process to modify pickup time using same logic as booking creation"""
    try:
        print("✅ BACKGROUND: Starting time modification...")
        print(f"📝 Time modification details: {time_string}")

        # Update database first (same as other modifications)
        update_booking_to_db(caller_number, updated_booking)
        print("✅ DATABASE UPDATED with new time")

        # Get order ID from booking storage (more reliable)
        stored_booking = booking_storage.get(caller_number, {})
        old_order_id = stored_booking.get("taxicaller_order_id")

        # Fallback to original booking if not in storage
        if not old_order_id and original_booking:
            old_order_id = original_booking.get("taxicaller_order_id")

        print(f"🛠️ DEBUG: old_order_id retrieved: {old_order_id}")

        if old_order_id:
            print(f"✅ CANCELLING OLD BOOKING: {old_order_id}")

            # Always cancel and recreate for time modifications (more reliable)
            cancel_success = cancel_taxicaller_booking(old_order_id)

            if cancel_success:
                print("✅ OLD BOOKING CANCELLED - creating new one")
                time.sleep(2)

                # Mark booking as modified
                updated_booking["modified_at"] = datetime.now(NZ_TZ).isoformat()
                updated_booking["ai_modified"] = True
                booking_storage[caller_number] = updated_booking

                # Create new booking using the same logic as booking creation
                success, response = send_booking_to_api(updated_booking, caller_number)

                if success:
                    print("✅ NEW BOOKING CREATED with new time")
                    # Store new order ID for future modifications
                    if response and "orderId" in response:
                        updated_booking["taxicaller_order_id"] = response["orderId"]
                        booking_storage[caller_number] = updated_booking
                        print(f"✅ NEW ORDER ID STORED: {response['orderId']}")

                    # Update database with new order ID
                    try:
                        update_booking_to_db(caller_number, updated_booking)
                        print("✅ DATABASE UPDATED with new order ID")
                    except Exception as db_error:
                        print(f"❌ DATABASE UPDATE FAILED: {db_error}")
                else:
                    print("❌ NEW BOOKING FAILED")
                    # Still keep the database updated even if TaxiCaller fails
                    try:
                        update_booking_to_db(caller_number, updated_booking)
                        print("✅ DATABASE UPDATED (TaxiCaller failed but DB updated)")
                    except Exception as db_error:
                        print(f"❌ DATABASE UPDATE ALSO FAILED: {db_error}")
            else:
                print("❌ CANCELLATION FAILED - cannot modify booking")
                # Still update database with time change
                try:
                    update_booking_to_db(caller_number, updated_booking)
                    print("✅ DATABASE UPDATED (TaxiCaller cancellation failed but DB updated)")
                except Exception as db_error:
                    print(f"❌ DATABASE UPDATE FAILED: {db_error}")
        else:
            print("❌ NO ORDER ID FOUND - cannot modify TaxiCaller booking")
            # Still update database with time change
            try:
                update_booking_to_db(caller_number, updated_booking)
                print("✅ DATABASE UPDATED (no TaxiCaller order to modify)")
            except Exception as db_error:
                print(f"❌ DATABASE UPDATE FAILED: {db_error}")

        print("✅ BACKGROUND: Time modification completed")
    except Exception as e:
        print(f"❌ BACKGROUND: Time modification error: {str(e)}")
        # Fallback: at least try to update the database
        try:
            update_booking_to_db(caller_number, updated_booking)
            print("✅ FALLBACK: Database updated despite error")
        except Exception as db_error:
            print(f"❌ FALLBACK: Database update also failed: {db_error}")

def parse_booking_speech(speech_text):
    """Parse booking speech using regex to extract details."""
    booking_data = {
        "name": "",
        "pickup_address": "",
        "destination": "",
        "pickup_time": "",
        "pickup_date": "",
        "raw_speech": speech_text,
    }

    # Extract name
    name_patterns = [
        r"my name is\s+([^,]+)",
        r"i'm\s+([^,]+)",
        r"i am\s+([^,]+)",
        r"it's\s+([^,]+)",
    ]

    for pattern in name_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            potential_name = match.group(1).strip()
            if not any(
                word in potential_name.lower()
                for word in [
                    "need", "want", "going", "from", "taxi", "booking",
                    "street", "road", "avenue", "lane", "drive"
                ]
            ):
                booking_data["name"] = potential_name
                break

    # Extract pickup address - FIXED to completely remove "number" and clean addresses
    pickup_patterns = [
        # Match number + street name + street type (remove "number" word)
        # Fallback patterns - UPDATED to handle "I am" as well as "I'm" and remove "number"
        r"(?:from|pick up from|pickup from)\s+(?:number\s+)?([^,]+?)(?:\s+(?:to|going|I'm|I am|and))",
        r"(?:from|pick up from|pickup from)\s+(?:number\s+)?([^,]+)$",
    ]

    for pattern in pickup_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            pickup = match.group(1).strip()
            pickup = pickup.replace(" I'm", "").replace(" I am", "").replace(" and", "")

            # AGGRESSIVE cleaning to remove "number" word completely
            pickup = re.sub(r"\bnumber\s+", "", pickup, flags=re.IGNORECASE)
            pickup = re.sub(r"\bright\s+now\b", "", pickup, flags=re.IGNORECASE).strip()

            # Fix common speech recognition errors
            pickup = pickup.replace("63rd Street Melbourne", "63 Hobart Street")
            pickup = pickup.replace("Melbourne Street", "Hobart Street")
            pickup = pickup.replace("mill street", "Willis Street")

            booking_data["pickup_address"] = pickup
            # AI Smart Cleaning - Remove time from pickup address
            if booking_data["pickup_address"]:
                pickup = booking_data["pickup_address"]
                # Remove patterns like "at 6 p.m.", "at 10:30 AM"
                pickup = re.sub(r'\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)', '', pickup, flags=re.IGNORECASE)
                # Remove time words
                pickup = re.sub(r'\s+(?:tomorrow|today|tonight|morning|afternoon|evening|now|asap).*$', '', pickup, flags=re.IGNORECASE)
                booking_data["pickup_address"] = pickup.strip()
            break
            
    # Extract destination - FIXED to completely remove "number" and clean up addresses
    destination = "railway station"  # This will be cleaned up by the mapping logic below
    destination_patterns = [
        r"(?:going to|to)\s+(railway station|train station|station)",
        # Handle "I am going to" specifically
        r"I am going to\s+(?:the\s+)?([^,]+?)(?:\s+(?:at\s+\d{1,2}|thank))",
        r"I'm going to\s+(?:the\s+)?([^,]+?)(?:\s+(?:at\s+\d{1,2}|thank))",
        # Handle "going to number X" pattern - capture without "number"
        r"(?:to|going to|going)\s+(?:the\s+)?([^,]+?)(?:\s+(?:tomorrow|today|tonight|at|\d{1,2}:|on|date|right now|now))",
        # Standard patterns without "number"
        r"(?:to|going to|going)\s+([^,]+?)(?:\s+(?:tomorrow|today|tonight|at|\d{1,2}:|on|date|right now|now))",
        # End of line patterns - capture without "number"
        r"(?:to|going to|going)\s+(?:number\s+)?(\d+\s+.+)$",
        r"(?:to|going to|going)\s+(.+)$",
    ]

    for pattern in destination_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            destination = match.group(1).strip()

            # AGGRESSIVE cleaning to remove "number" and fix order
            destination = re.sub(r"\bnumber\s+", "", destination, flags=re.IGNORECASE)

            # Fix address order: "Miramar number 63 Hobart Street" → "63 Hobart Street, Miramar"
            miramar_fix = re.search(
                r"(miramar)\s+(?:number\s+)?(\d+\s+\w+\s+street)",
                destination,
                re.IGNORECASE,
            )
            if miramar_fix:
                destination = f"{miramar_fix.group(2)}, {miramar_fix.group(1)}"

            # Other area fixes
            destination = destination.replace("wellington wellington", "wellington")
            destination = re.sub(r"\s+(at|around|by)\s+\d+", "", destination)

            # FIXED Smart destination mapping - ONLY for generic terms
            if destination.lower() in ["hospital", "the hospital"]:
                destination = "Wellington Hospital"
            elif any(airport_word in destination.lower() for airport_word in [
                "airport", "the airport", "domestic airport", "international airport", 
                "steward duff", "stewart duff", "wlg airport", "wellington airport"
            ]):
                destination = "Wellington Airport"
            elif destination.lower() in ["station", "railway station", "train station", "the station"]:
                destination = "Wellington Railway Station"
            elif "te papa" in destination.lower():
                destination = "Te Papa Museum"
            # For specific hospitals like "Hutt Hospital", "Bowen Hospital" - keep as-is!

        booking_data["destination"] = destination
        # AI Smart Cleaning - Remove time from destination
        if booking_data["destination"]:
            dest = booking_data["destination"]
            # Remove time patterns
            dest = re.sub(r'\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)', '', dest, flags=re.IGNORECASE)
            dest = re.sub(r'\s+by\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)', '', dest, flags=re.IGNORECASE)
            booking_data["destination"] = dest.strip()
        break

    # Extract date - FIXED DATE PARSING BUG
    immediate_keywords = [
        "right now", "now", "asap", "as soon as possible", "immediately", "straight away",
    ]
    tomorrow_keywords = [
        "tomorrow morning", "tomorrow afternoon", "tomorrow evening", "tomorrow night", "tomorrow",
    ]
    today_keywords = [
        "tonight", "today", "later today", "this afternoon", "this evening", "this morning",
    ]
    after_tomorrow_keywords = [
        "after tomorrow", "day after tomorrow", "2 days", "two days"
    ]
    
    # First check for specific date mentions (22nd, 23rd, etc.)
    date_pattern = r"(\d{1,2})(?:st|nd|rd|th)"
    date_match = re.search(date_pattern, speech_text)

    if any(keyword in speech_text.lower() for keyword in immediate_keywords):
        current_time = datetime.now(NZ_TZ)
        booking_data["pickup_date"] = current_time.strftime("%d/%m/%Y")
        booking_data["pickup_time"] = "ASAP"
    elif any(keyword in speech_text.lower() for keyword in after_tomorrow_keywords):
        # Handle "after tomorrow" - add 2 days
        after_tomorrow = datetime.now(NZ_TZ) + timedelta(days=2)
        booking_data["pickup_date"] = after_tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in tomorrow_keywords):
        # Handle "tomorrow" - add 1 day
        tomorrow = datetime.now(NZ_TZ) + timedelta(days=1)
        booking_data["pickup_date"] = tomorrow.strftime("%d/%m/%Y")
    elif date_match:
        # Customer specified a specific date number - FIXED BUG HERE
        day = int(date_match.group(1))
        current_date = datetime.now(NZ_TZ)
        current_month = current_date.month
        current_year = current_date.year
        # If the day has already passed this month, assume next month
        if day < current_date.day:
            if current_month == 12:
                current_month = 1
                current_year += 1
            else:
                current_month += 1
        # FIXED: Use the correct variables for the date
        booking_data["pickup_date"] = datetime(current_year, current_month, day).strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in today_keywords):
        today = datetime.now(NZ_TZ)
        booking_data["pickup_date"] = today.strftime("%d/%m/%Y")

    # Extract time
    time_patterns = [
        r"in\s+(\d+)\s+minutes?",  # NEW: matches "in 30 minutes"
        r"in\s+(\d+)\s+hours?",    # NEW: matches "in 2 hours"
        r"time\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
    ]

    # Add special handling for "half hour" and "midday/noon" BEFORE the pattern matching
    if any(phrase in speech_text.lower() for phrase in ["half hour", "half an hour", "30 minutes"]):
        booking_time = datetime.now(NZ_TZ) + timedelta(minutes=30)
        booking_data["pickup_time"] = booking_time.strftime('%H:%M')  # Use 24-hour format
        booking_data["pickup_date"] = datetime.now(NZ_TZ).strftime("%d/%m/%Y")
    elif any(phrase in speech_text.lower() for phrase in ["midday", "noon", "12 noon", "12 midday"]):
        # Handle midday/noon as 12:00 PM (12:00 in 24-hour format)
        booking_data["pickup_time"] = "12:00"
        # Use today's date unless another date is specified
        if not booking_data.get("pickup_date"):
            booking_data["pickup_date"] = datetime.now(NZ_TZ).strftime("%d/%m/%Y")
    elif not any(keyword in speech_text.lower() for keyword in immediate_keywords):
        # Then do the pattern matching
        for pattern in time_patterns:
            match = re.search(pattern, speech_text, re.IGNORECASE)
            if match:
                if pattern == r"in\s+(\d+)\s+minutes?":
                    minutes = int(match.group(1))
                    booking_time = datetime.now(NZ_TZ) + timedelta(minutes=minutes)
                    time_str = booking_time.strftime('%H:%M')  # Use 24-hour format
                    booking_data["pickup_time"] = time_str
                    booking_data["pickup_date"] = datetime.now(NZ_TZ).strftime("%d/%m/%Y")
                    break
                elif pattern == r"in\s+(\d+)\s+hours?":
                    hours = int(match.group(1))
                    booking_time = datetime.now(NZ_TZ) + timedelta(hours=hours)
                    time_str = booking_time.strftime('%H:%M')  # Use 24-hour format
                    booking_data["pickup_time"] = time_str
                    booking_data["pickup_date"] = datetime.now(NZ_TZ).strftime("%d/%m/%Y")
                    break
                else:
                    # Handle regular time patterns (4 PM, etc.)
                    time_str = match.group(1).strip()
                    time_str = time_str.replace("p.m.", "PM").replace("a.m.", "AM")

                    # Add :00 if no minutes specified
                    if ":" not in time_str and any(x in time_str for x in ["AM", "PM"]):
                        time_str = time_str.replace(" AM", ":00 AM").replace(" PM", ":00 PM")

                    # Convert to 24-hour format for consistent storage
                    if "PM" in time_str:
                        # Handle PM times
                        hour_part = time_str.split(":")[0].strip()
                        minute_part = time_str.split(":")[1].replace("PM", "").strip() if ":" in time_str else "00"
                        hour = int(hour_part)
                        if hour != 12:  # 12 PM stays as 12
                            hour += 12
                        time_str = f"{hour:02d}:{minute_part}"
                    elif "AM" in time_str:
                        # Handle AM times
                        hour_part = time_str.split(":")[0].strip()
                        minute_part = time_str.split(":")[1].replace("AM", "").strip() if ":" in time_str else "00"
                        hour = int(hour_part)
                        if hour == 12:  # 12 AM becomes 00
                            hour = 0
                        time_str = f"{hour:02d}:{minute_part}"

                    booking_data["pickup_time"] = time_str
                    break
    
    # Clean temporal words from addresses
    time_words = ['tomorrow', 'today', 'tonight', 'morning', 'afternoon', 'evening', 'right now', 'now', 'asap']


# Clean and validate pickup address
    if booking_data.get('pickup_address'):
        pickup = booking_data['pickup_address']
        # Remove time words
        for word in time_words:
            pickup = pickup.replace(f" {word}", "")
        # Fix "in Wellington CBD" to ", Wellington CBD"
        pickup = pickup.replace(" in Wellington CBD", ", Wellington CBD")
        
        # Validate with Google Maps
        if gmaps:
            validated_pickup = validate_and_format_address(pickup, "pickup")
            # Only use validated address if it's a string (not False)
            if validated_pickup and isinstance(validated_pickup, str):
                pickup = validated_pickup
        booking_data['pickup_address'] = pickup.strip()
    
    # Clean and validate destination
    if booking_data.get('destination'):
        destination = booking_data['destination']
        # Remove time words
        for word in time_words:
            destination = destination.replace(f" {word}", "")
        # Fix "in Wellington CBD" to ", Wellington CBD"  
        destination = destination.replace(" in Wellington CBD", ", Wellington CBD")
        
        # Validate with Google Maps
        if gmaps:
            validated_destination = validate_and_format_address(destination, "destination")
            # Only use validated address if it's a string (not False)
            if validated_destination and isinstance(validated_destination, str):
                destination = validated_destination
        booking_data['destination'] = destination.strip()
    
    print(f"📝 PARSED BOOKING DATA: {booking_data}")
    return booking_data

def send_booking_to_api(booking_data, caller_number):
    """STEP 2 & 3: Send booking to TaxiCaller dispatch system with reduced timeout"""
    
    # STEP 3: Format the input data - ensure we extract name, pickup, dropoff, time/date
    enhanced_booking_data = {
        "customer_name": booking_data.get("name", ""),
        "phone": caller_number,
        "pickup_address": booking_data.get("pickup_address", ""),
        "destination": booking_data.get("destination", ""),
        "pickup_time": booking_data.get("pickup_time", ""),
        "pickup_date": booking_data.get("pickup_date", ""),
        "booking_reference": f"AI_{caller_number.replace('+', '').replace('-', '').replace(' ', '')}_{int(time.time())}",
        "service": "taxi",
        "created_via": "ai_ivr",
        "raw_speech": booking_data.get("raw_speech", ""),
        "booking_status": "confirmed",
        "payment_method": "cash",
        "number_of_passengers": 1,
        "special_instructions": f"AI IVR booking - {booking_data.get('raw_speech', '')}",
        "created_at": datetime.now(NZ_TZ).isoformat(),
        "is_immediate": booking_data.get("pickup_time", "").upper() in ["ASAP", "NOW", "IMMEDIATELY"]
    }
    
    print(f"📤 QUICK BOOKING SUBMISSION:")
    print(f"   Name: {enhanced_booking_data['customer_name']}")
    print(f"   From: {enhanced_booking_data['pickup_address']}")
    print(f"   To: {enhanced_booking_data['destination']}")
    print(f"   Time: {enhanced_booking_data['pickup_time']}")

    # STEP 2: Try TaxiCaller with quick timeout (don't make customer wait)
    if TAXICALLER_API_KEY:
        print(f"🚖 QUICK TAXICALLER ATTEMPT")
        try:
            success, response = send_booking_to_taxicaller(booking_data, caller_number)
            if success:
                print(f"✅ TAXICALLER SUCCESS")
                return success, response
            else:
                print("❌ TAXICALLER FAILED - using fallback")
        except Exception as e:
            print(f"❌ TAXICALLER ERROR: {str(e)} - using fallback")

    # Quick fallback to Render endpoint
    try:
        print(f"📡 QUICK RENDER FALLBACK")

        response = requests.post(
            RENDER_ENDPOINT,
            json=enhanced_booking_data,
            timeout=3,  # Very short timeout - don't make customer wait
            headers={
                "Content-Type": "application/json",
                "User-Agent": "KiwiCabs-AI-IVR/2.1",
            },
        )

        if response.status_code in [200, 201]:
            print(f"✅ RENDER SUCCESS")
            return True, response.json()
        else:
            print(f"❌ RENDER FAILED: {response.status_code}")
            return True, {"status": "accepted"}  # Return success anyway

    except requests.Timeout:
        print(f"⚠️ RENDER TIMEOUT - assuming success")
        return True, {"status": "timeout_assumed_success"}
    except Exception as e:
        print(f"❌ RENDER ERROR: {str(e)} - assuming success")
        return True, {"status": "error_assumed_success"}

def validate_wellington_service_area(caller_location, booking_addresses=None):
    """Validate service area - simplified for reliability"""
    # For now, assume all calls are valid unless clearly outside Wellington
    if booking_addresses:
        for address_type, address in booking_addresses.items():
            if address:
                address_lower = address.lower()
                outside_cities = [
                    "auckland",
                    "christchurch",
                    "hamilton",
                    "melbourne",
                    "sydney",
                ]
                if any(city in address_lower for city in outside_cities):
                    return {
                        "in_service_area": False,
                        "reason": f"booking_{address_type}_outside_wellington",
                        "message": f"Sorry, Kiwi Cabs operates only in the Wellington region. Your {address_type} appears to be outside our service area.",
                    }

    return {
        "in_service_area": True,
        "reason": "wellington_region_confirmed",
        "message": None,
    }

def redirect_to(path):
    """Helper function to create redirect responses"""
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")









# Routes
@app.route("/", methods=["GET"])
def index():
    """Root endpoint"""
    return {
        "status": "running",
        "service": "Kiwi Cabs AI Service",
        "version": "2.2-immediate-dispatch",
        "taxicaller_configured": bool(TAXICALLER_API_KEY),
        "taxicaller_key_preview": TAXICALLER_API_KEY[:8] + "..."
        if TAXICALLER_API_KEY
        else None,
        "database_connected": get_db_connection() is not None,
        "features": [
            "immediate_dispatch_for_urgent",
            "fast_confirmation",
            "clean_addresses",
            "database_storage",
            "smart_wellington_poi_recognition"
        ],
    }, 200
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Kiwi Cabs Booking Service",
        "version": "2.2-immediate-dispatch",
        "google_speech": GOOGLE_SPEECH_AVAILABLE,
        "taxicaller_api": bool(TAXICALLER_API_KEY),
        "taxicaller_key_preview": TAXICALLER_API_KEY[:8] + "..."
        if TAXICALLER_API_KEY
        else None,
        "database": get_db_connection() is not None,
        "current_time": datetime.now(NZ_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
    }, 200


@app.route("/voice", methods=["POST"])
def voice():
    """Main voice entry point"""
    print("🎯 Voice endpoint called!")
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/menu" method="POST" timeout="10" numDigits="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Kia ora, and welcome to Kiwi Cabs.
            Please listen carefully as we have upgraded our booking system.
            I'm your AI assistant, here to help you book your taxi.
            This call may be recorded for training and security purposes.
            Press 1 for a new taxi booking.
            Press 2 to change or cancel an existing booking.
            Press 3 to speak with our team.
            Press 4 If you have a complaint or have lost an item in one of our taxis
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/menu", methods=["POST"])
def menu():
    """Handle keypad menu selection"""
    digits = request.form.get("Digits", "")
    print(f"📞 Menu selection: {digits}")

    if digits == "1":
        return redirect_to("/book_taxi")
    elif digits == "2":
        return redirect_to("/modify_booking")
    elif digits == "3":
        return redirect_to("/team")
    elif digits == "4":
        return redirect_to("/email_support")
    else:
        return redirect_to("/voice")


@app.route("/book_taxi", methods=["POST"])
def book_taxi():
    """Start taxi booking process - STEP-BY-STEP FLOW"""
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    print(f"🚖 Starting step-by-step booking for call: {call_sid}")
    
    # Initialize session for this call
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {
            "booking_step": "name",
            "partial_booking": {
                "name": "",
                "pickup_address": "",
                "destination": "",
                "pickup_time": "",
                "pickup_date": "",
                "raw_speech": ""
            },
            "caller_number": caller_number
        }
    
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I'll help you book your taxi.
        Please tell me your name.
    </Say>
    <Gather input="speech" 
            action="/process_booking" 
            method="POST" 
            timeout="10" 
            language="en-NZ" 
            speechTimeout="1" 
            finishOnKey="" 
            enhanced="true">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
    <Redirect>/book_taxi</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/process_booking", methods=["POST"])
def process_booking():
    """Process booking speech input - STEP-BY-STEP LOGIC"""
    speech_data = request.form.get("SpeechResult", "")
    confidence = float(request.form.get("Confidence", "0"))
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    print(f"🎯 SPEECH: '{speech_data}' (Confidence: {confidence:.2f})")

    # Save conversation to database
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO conversations (phone_number, message, role) VALUES (%s, %s, %s)",
                (caller_number, speech_data, "user"),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"❌ Error saving conversation: {e}")
            if conn:
                conn.close()

    # Get or create session
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {
            "booking_step": "name",
            "partial_booking": {
                "name": "",
                "pickup_address": "",
                "destination": "",
                "pickup_time": "",
                "pickup_date": "",
                "raw_speech": ""
            },
            "caller_number": caller_number
        }
    
    session = user_sessions[call_sid]
    current_step = session.get("booking_step", "name")
    partial_booking = session.get("partial_booking", {})
    
    # Add current speech to raw speech
    partial_booking["raw_speech"] = f"{partial_booking.get('raw_speech', '')} {speech_data}".strip()
    
    print(f"📋 CURRENT STEP: {current_step}")
    
    # Process based on current step
    if current_step == "name":
        # Extract name from speech
        name = speech_data.strip()
        
        # Clean common phrases
        name_lower = name.lower()
        if name_lower.startswith("my name is "):
            name = name[11:].strip()
        elif name_lower.startswith("i am "):
            name = name[5:].strip()
        elif name_lower.startswith("i'm "):
            name = name[4:].strip()
        elif name_lower.startswith("it's "):
            name = name[5:].strip()
        elif name_lower.startswith("this is "):
            name = name[8:].strip()
        
        # Capitalize properly
        name = ' '.join(word.capitalize() for word in name.split())
        
        if len(name) >= 2 and not any(char.isdigit() for char in name):
            partial_booking["name"] = name
            session["booking_step"] = "pickup"
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Nice to meet you {name}! 
        What's your pickup address?
        For example unit 1 at 27 melrose road.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me where to pick you up.</Say>
    </Gather>
</Response>"""
        else:
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't catch your name. Could you please tell me your name?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="10" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""
    
    elif current_step == "pickup":
        # Process pickup address
        pickup = speech_data.strip()
        
        # Clean common prefixes
        pickup_lower = pickup.lower()
        if pickup_lower.startswith("from "):
            pickup = pickup[5:].strip()
        elif pickup_lower.startswith("at "):
            pickup = pickup[3:].strip()
        elif pickup_lower.startswith("pickup from "):
            pickup = pickup[12:].strip()
        elif pickup_lower.startswith("pick me up at "):
            pickup = pickup[14:].strip()
        elif pickup_lower.startswith("pick me up from "):
            pickup = pickup[16:].strip()
        
        
        # Remove "number" word
        pickup = re.sub(r"\bnumber\s+", "", pickup, flags=re.IGNORECASE)
        
        if len(pickup) >= 5:
            # Check for airport pickup
            if any(keyword in pickup.lower() for keyword in ["airport", "terminal"]):
                response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        You don't need to book a taxi from the airport as we have taxis waiting at the airport rank.
        We appreciate your booking with Kiwi Cabs. Have a great day. Goodbye!
    </Say>
    <Hangup/>
</Response>"""
                return Response(response, mimetype="text/xml")

            # Parse address to get clean and full versions
            try:
                clean_pickup, full_pickup = parse_address(pickup)
                print(f"📍 Parsed pickup - Clean: {clean_pickup}, Full: {full_pickup}")

                # Use full address for validation and storage
                address_to_validate = full_pickup if full_pickup else pickup
                if gmaps:
                    validated_address = validate_and_format_address(address_to_validate, "pickup")
                else:
                    validated_address = address_to_validate
                
                if(validated_address == False):
                    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Address not recognized. Could you please tell me your pickup address again?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""
                    return Response(response, mimetype="text/xml")
                # Use clean address for speech
                pickup_for_speech = clean_pickup if clean_pickup else clean_address_for_speech(validated_address)

            except Exception as e:
                print(f"⚠️ Error parsing pickup address: {e}")
                # Fallback to original logic
                if gmaps:
                    validated_address = validate_and_format_address(pickup, "pickup")
                else:
                    validated_address = pickup
                pickup_for_speech = clean_address_for_speech(validated_address)
                clean_pickup = pickup_for_speech  # Set clean address for fallback

            # Save both full and clean addresses
            partial_booking["pickup_address"] = validated_address
            partial_booking["pickup_address_clean"] = pickup_for_speech
            session["booking_step"] = "destination"

            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! I have your pickup at {pickup_for_speech}.
        Where would you like to go?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me your destination.</Say>
    </Gather>
</Response>"""
        else:
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't catch that. Could you please tell me your pickup address?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""
    
    elif current_step == "destination":
        # Process destination using AI POI resolution
        destination = speech_data.strip()
        
        # Clean common prefixes
        dest_lower = destination.lower()
        if dest_lower.startswith("to "):
            destination = destination[3:].strip()
        elif dest_lower.startswith("going to "):
            destination = destination[9:].strip()
        elif dest_lower.startswith("take me to "):
            destination = destination[11:].strip()
        elif dest_lower.startswith("i'm going to "):
            destination = destination[13:].strip()
        elif dest_lower.startswith("i am going to "):
            destination = destination[14:].strip()
        
        # Parse address to get clean and full versions
        try:
            clean_destination, full_destination = parse_address(destination)
            print(f"📍 Parsed destination - Clean: {clean_destination}, Full: {full_destination}")

            # Use full address for POI resolution
            address_to_resolve = full_destination if full_destination else destination

        except Exception as e:
            print(f"⚠️ Error parsing destination address: {e}")
            clean_destination = None
            address_to_resolve = destination

        # SMART WELLINGTON POI RESOLUTION
        print(f"🔍 Resolving destination POI: {address_to_resolve}")
        resolved_destination = resolve_wellington_poi_to_address(address_to_resolve)

        if(resolved_destination == False):
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Address not recognized. Where would you like to go?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""
            return Response(response, mimetype="text/xml")


        if isinstance(resolved_destination, dict) and resolved_destination.get('full_address'):
            partial_booking["destination"] = resolved_destination["full_address"]

            # Use clean address for speech, fallback to resolved speech
            destination_for_speech = clean_destination if clean_destination else resolved_destination['speech']
            partial_booking["destination_clean"] = destination_for_speech

            session["booking_step"] = "time"

            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! Going to {destination_for_speech}.
        When do you need the taxi?
        You can say things like "now", "in 30 minutes", "at 3 PM", or "tomorrow morning".
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me when you need the taxi.</Say>
    </Gather>
</Response>"""
        elif isinstance(resolved_destination, str) and len(resolved_destination) >= 3:
            partial_booking["destination"] = resolved_destination

            # Use clean address for speech, fallback to resolved destination
            destination_for_speech = clean_destination if clean_destination else clean_address_for_speech(resolved_destination)
            partial_booking["destination_clean"] = destination_for_speech

            session["booking_step"] = "time"

            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! Going to {destination_for_speech}.
        When do you need the taxi?
        You can say things like "now", "in 30 minutes", "at 3 PM", or "tomorrow morning".
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me when you need the taxi.</Say>
    </Gather>
</Response>"""
        else:
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't catch that. Where would you like to go?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""
    
    elif current_step == "time":
        # Process time
        time_text = speech_data.lower().strip()
        time_string = ""
        valid_time = False
        
        # Check for immediate booking
        immediate_keywords = ["now", "right now", "immediately", "asap", "as soon as possible", "straight away"]
        if any(keyword in time_text for keyword in immediate_keywords):
            partial_booking["pickup_time"] = "ASAP"
            partial_booking["pickup_date"] = datetime.now(NZ_TZ).strftime("%d/%m/%Y")
            time_string = "right now"
            valid_time = True
        else:
            # Parse time using existing logic

            parsed_booking = parse_booking_speech(speech_data)
            
            if parsed_booking.get("pickup_time"):
                partial_booking["pickup_time"] = parsed_booking["pickup_time"]
                formatted_time = format_time_for_speech(parsed_booking['pickup_time'])
                if parsed_booking.get("pickup_date"):
                    partial_booking["pickup_date"] = parsed_booking["pickup_date"]
                    time_string = f"on {parsed_booking['pickup_date']} at {formatted_time}"
                else:
                    # Default to today if no date specified
                    partial_booking["pickup_date"] = datetime.now(NZ_TZ).strftime("%d/%m/%Y")
                    time_string = f"today at {formatted_time}"

                valid_time = True
                
                datetime_str = f"{partial_booking['pickup_date']} {partial_booking['pickup_time']}"
                try:
                    booked_time = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
                    booked_time = booked_time.replace(tzinfo=ZoneInfo("Pacific/Auckland"))
                except ValueError as e:
                    print(f"❌ Error parsing datetime '{datetime_str}': {e}")
                    # If parsing fails, ask for time again
                    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't understand the time. Could you please tell me when you need the taxi?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""
                    return Response(response, mimetype="text/xml")
                if(booked_time < datetime.now(NZ_TZ)):
                    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        That time is in the past. Would you like to pick a different time?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listning.</Say>
    </Gather>
</Response>"""
                    return Response(response, mimetype="text/xml")

                
            elif parsed_booking.get("pickup_date"):
                # Date specified but no time - ask for time
                partial_booking["pickup_date"] = parsed_booking["pickup_date"]
                response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't catch that. Please tell me when you need the taxi again.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listning.</Say>
    </Gather>
</Response>"""
                # Store session updates before returning
                session["partial_booking"] = partial_booking
                user_sessions[call_sid] = session
                return Response(response, mimetype="text/xml")
        
        if valid_time:
            session["booking_step"] = "driver_instructions"
            
            # Simple transition to driver instructions  
            instructions_prompt = f"Great {partial_booking['name']}! Your taxi is booked for {time_string}."    

            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {instructions_prompt}
        Do you have any special instructions for the driver?
        For example, "wait for me", "call when you arrive", "Text on arrival" or just say "no instructions".
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Any instructions for the driver?</Say>
    </Gather>
</Response>"""
        else:
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't understand the time. 
        Could you please tell me when you need the taxi?
        For example, say "now", "in 30 minutes", or "at 3 PM".
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""


    elif current_step == "driver_instructions":
        # Process driver instructions
        instructions = speech_data.strip()

        # Check if they have instructions or said no
        instructions_lower = instructions.lower()
        if any(word in instructions_lower for word in ["no", "nothing", "none", "nope", "no instructions", "no instruction"]):
            partial_booking["driver_instructions"] = ""
            instructions_msg = ""
        else:
            partial_booking["driver_instructions"] = instructions
            instructions_msg = f", with instructions: {instructions}"

        session["booking_step"] = "confirmation"
        
        # Build final confirmation
        name = partial_booking['name']
        confirmation_text = f"Perfect {name}! Let me confirm everything: "

        # Use saved clean addresses from partial_booking
        pickup_for_speech = partial_booking.get('pickup_address_clean', clean_address_for_speech(partial_booking['pickup_address']))
        destination_for_speech = partial_booking.get('destination_clean', clean_address_for_speech(partial_booking.get('destination', '')))

        confirmation_text += f"pickup from {pickup_for_speech}, "
        confirmation_text += f"going to {destination_for_speech},"
        
        if partial_booking.get("pickup_time") == "ASAP":
            confirmation_text += " right now"
        else:
            pickup_date = partial_booking.get('pickup_date', '')
            pickup_time = partial_booking.get('pickup_time', '')
            if pickup_date and pickup_time:
                formatted_time = format_time_for_speech(pickup_time)
                confirmation_text += f" on {pickup_date} at {formatted_time}"
        
        confirmation_text += instructions_msg

        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/confirm_booking" input="speech" method="POST" timeout="10" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            {confirmation_text}.
            Is everything correct? Say yes to confirm or no to start over.
        </Say>
    </Gather>
    <Redirect>/process_booking</Redirect>
</Response>"""
    else:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't understand. 
        Let's start over with your booking.
        Please tell me your name.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""

    # Store session updates
    session["partial_booking"] = partial_booking
    user_sessions[call_sid] = session
    
    # Store in pending for confirmation step
    if current_step == "driver_instructions":
        user_sessions[call_sid]["pending_booking"] = partial_booking
        user_sessions[call_sid]["caller_number"] = caller_number
    
    return Response(response, mimetype="text/xml")





@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Handle booking confirmation with immediate dispatch for urgent bookings"""
    speech_result = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    print(f"🔔 Confirmation response: '{speech_result}'")

    session_data = user_sessions.get(call_sid, {})
    booking_data = session_data.get("pending_booking", {})

    if not booking_data:
        print("❌ No pending booking found")
        return redirect_to("/book_taxi")

    # Check for yes/confirm - Look for "yes" anywhere in the response
    if any(
        word in speech_result
        for word in ["yes", "confirm", "correct", "right", "ok", "okay", "yep", "yeah"]
    ):
        print("✅ Booking confirmed - processing immediately")

        # Store booking immediately
        booking_storage[caller_number] = {
            **booking_data,
            "confirmed_at": datetime.now(NZ_TZ).isoformat(),
            "status": "confirmed",
        }

        # Save to database
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()

                # Update or insert customer
                cur.execute(
                    """INSERT INTO customers (phone_number, name) 
                    VALUES (%s, %s) 
                    ON CONFLICT (phone_number) 
                    DO UPDATE SET name = EXCLUDED.name, total_bookings = customers.total_bookings + 1""",
                    (caller_number, booking_data["name"]),
                )

                # Insert booking
                is_immediate = booking_data.get("pickup_time", "").upper() in [
                    "ASAP",
                    "NOW",
                    "IMMEDIATELY",
                ]
                scheduled_time = None

                if (
                    not is_immediate
                    and booking_data.get("pickup_date")
                    and booking_data.get("pickup_time")
                ):
                    try:
                        # Parse date and time for scheduled bookings
                        date_parts = booking_data["pickup_date"].split("/")
                        time_str = booking_data["pickup_time"]
                        if "AM" in time_str or "PM" in time_str:
                            pickup_time = datetime.strptime(time_str, "%I:%M %p").time()
                        else:
                            pickup_time = datetime.strptime(time_str, "%H:%M").time()

                        scheduled_time = datetime.combine(
                            datetime(
                                int(date_parts[2]),
                                int(date_parts[1]),
                                int(date_parts[0]),
                            ).date(),
                            pickup_time,
                        )
                    except Exception as e:
                        print(f"❌ Error parsing scheduled time: {e}")
                        pass

                cur.execute(
                    """INSERT INTO bookings 
                    (customer_phone, customer_name, pickup_location, dropoff_location, 
                        scheduled_time, status, booking_reference, raw_speech, 
                        pickup_date, pickup_time, created_via) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        caller_number,
                        booking_data["name"],
                        booking_data["pickup_address"],
                        booking_data["destination"],
                        scheduled_time,
                        "confirmed",
                        f"AI_{caller_number.replace('+', '')}_{int(time.time())}",
                        booking_data.get("raw_speech", ""),
                        booking_data.get("pickup_date", ""),
                        booking_data.get("pickup_time", ""),
                        "ai_ivr",
                    ),
                )

                conn.commit()
                cur.close()
                conn.close()
                print("✅ Booking saved to database")
            except Exception as e:
                print(f"❌ Database error: {e}")
                if conn:
                    conn.close()

        # Check if this is an IMMEDIATE booking (right now, ASAP, now)
        is_immediate = booking_data.get("pickup_time", "").upper() in [
            "ASAP",
            "NOW",
            "IMMEDIATELY",
        ]
        has_immediate_words = any(
            word in booking_data.get("raw_speech", "").lower()
            for word in [
                "right now",
                "now",
                "asap",
                "immediately",
                "straight away",
                "as soon as possible",
            ]
        )

        if is_immediate or has_immediate_words:
            print(
                "🚨 IMMEDIATE BOOKING - Dispatching to TaxiCaller NOW before responding to customer"
            )

            try:
                # IMMEDIATE dispatch - don't use background thread for urgent bookings
                success, api_response = send_booking_to_api(booking_data, caller_number)
                if success:
                    print(f"✅ IMMEDIATE DISPATCH SUCCESS - booking sent to TaxiCaller")
                    immediate_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Your urgent booking has been dispatched immediately to our drivers.
        We appreciate your booking with Kiwi Cabs. Have a great day.
        Goodbye!
    </Say>
    <Hangup/>
</Response>"""
                else:
                    print(f"❌ IMMEDIATE DISPATCH FAILED - but booking recorded")
                    immediate_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Your booking has been created successfully.
        We appreciate your booking with Kiwi Cabs. Have a great day.
        Goodbye!
    </Say>
    <Hangup/>
</Response>"""
            except Exception as e:
                print(f"❌ IMMEDIATE DISPATCH ERROR: {str(e)}")
                immediate_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Your booking has been created successfully.
        We appreciate your booking with Kiwi Cabs. Have a great day.
        Goodbye!
    </Say>
    <Hangup/>
</Response>"""
        else:
            print("📅 SCHEDULED BOOKING - Using background processing")

            # IMMEDIATE response for scheduled bookings
            immediate_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Your booking has been created successfully.
        We appreciate your booking with Kiwi Cabs. Have a great day.
        Goodbye!
    </Say>
    <Hangup/>
</Response>"""

            # Send scheduled bookings in background
            def background_api():
                try:
                    print(f"📤 Background processing for scheduled booking...")
                    send_booking_to_api(booking_data, caller_number)
                    print(f"✅ Background processing completed")
                except Exception as e:
                    print(f"⚠️ Background processing error: {str(e)}")

            # Start background thread for non-urgent bookings
            threading.Thread(target=background_api, daemon=True).start()

        # Clear session
        if call_sid in user_sessions:
            del user_sessions[call_sid]

        return Response(immediate_response, mimetype="text/xml")

    elif any(word in speech_result for word in ["no", "wrong", "change", "different", "start over"]):
        print("❌ Booking rejected - starting over")
        
        # Reset session to start from name
        if call_sid in user_sessions:
            user_sessions[call_sid] = {
                "booking_step": "name",
                "partial_booking": {
                    "name": "",
                    "pickup_address": "",
                    "destination": "",
                    "pickup_time": "",
                    "pickup_date": "",
                    "raw_speech": ""
                },
                "caller_number": caller_number
            }
        
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No problem. Let's start over.
        Please tell me your name.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="10" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
</Response>"""
    else:
        print("❓ Unclear response - asking again with simpler question")
        
        # Build simple confirmation
        booking = session_data.get("pending_booking", {})

        # Use saved clean addresses from booking, fallback to parsing if not available
        pickup_for_speech = booking.get('pickup_address_clean', clean_address_for_speech(booking.get('pickup_address', '')))
        destination_for_speech = booking.get('destination_clean', clean_address_for_speech(booking.get('destination', '')))

        simple_confirm = f"Is this booking correct? {booking.get('name', '')}, from {pickup_for_speech} to {destination_for_speech}"
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/confirm_booking" input="speech" method="POST" timeout="10" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            {simple_confirm}? Say YES or NO.
        </Say>
    </Gather>
    <Redirect>/confirm_booking</Redirect>
</Response>"""

    return Response(response, mimetype="text/xml")

@app.route("/modify_booking", methods=["POST"])
def modify_booking():
    """Handle booking modifications - AI powered with natural language"""
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    print(f"📞 Checking bookings for: {caller_number}")

    # Check database first
    conn = get_db_connection()
    booking = None

    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT * FROM bookings 
                WHERE customer_phone = %s AND status = 'confirmed' 
                ORDER BY booking_time DESC LIMIT 1""",
                (caller_number,),
            )
            db_booking = cur.fetchone()

            if db_booking:
                booking = {
                    "name": db_booking["customer_name"],
                    "pickup_address": db_booking["pickup_location"],
                    "destination": db_booking["dropoff_location"],
                    "pickup_date": db_booking["pickup_date"],
                    "pickup_time": db_booking["pickup_time"],
                    "status": db_booking["status"],
                    "booking_reference": db_booking["booking_reference"],
                }

            cur.close()
            conn.close()
        except Exception as e:
            print(f"❌ Database error: {e}")
            if conn:
                conn.close()

    # Fallback to memory storage
    if (
        not booking
        and caller_number in booking_storage
        and booking_storage[caller_number].get("status") == "confirmed"
    ):
        booking = booking_storage[caller_number]

    if booking:
        # Store in session for modification
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]["modifying_booking"] = booking.copy()
        user_sessions[call_sid]["caller_number"] = caller_number

        # Format booking details
        name = booking.get("name", "Customer")
        pickup_date = booking.get("pickup_date", "")
        pickup_time = booking.get("pickup_time", "")

        # Use saved clean addresses from booking, fallback to parsing if not available
        pickup = booking.get("pickup_address_clean", clean_address_for_speech(booking.get("pickup_address", "")))
        destination = booking.get("destination_clean", clean_address_for_speech(booking.get("destination", "")))

        print(f"clean address for speech cleaned2: {pickup}")
        # Build time string
        time_str = ""
        if pickup_time == "ASAP":
            time_str = "as soon as possible"
        elif pickup_date and pickup_time:
            formatted_time = format_time_for_speech(pickup_time)
            time_str = f"on {pickup_date} at {formatted_time}"
        elif pickup_time:
            formatted_time = format_time_for_speech(pickup_time)
            time_str = f"at {formatted_time}"

        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    
    <Gather action="/modification_menu" method="POST" timeout="10" numDigits="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Hello {name}, I found your booking.
            You have a taxi from {pickup} to {destination} {time_str}.
            What would you like to change?
            Press 1 for changing the time.
            Press 2 for changing pickup location.
            Press 3 for changing destination.
            Press 4 for cancel the booking.
        </Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
    else:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I couldn't find any active booking for your phone number.
        Would you like to make a new booking?
    </Say>
    <Gather input="speech" action="/no_booking_found" method="POST" timeout="10" language="en-NZ" speechTimeout="1">
    </Gather>
</Response>"""

    return Response(response, mimetype="text/xml")

@app.route("/no_booking_found", methods=["POST"])
def no_booking_found():
    """Handle case when no booking found"""
    speech_result = request.form.get("SpeechResult", "").lower()

    if any(
        word in speech_result for word in ["yes", "yeah", "yep", "book", "new", "make"]
    ):
        return redirect_to("/book_taxi")
    else:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! We appreciate your booking with Kiwi Cabs. Have a great day!
    </Say>
    <Hangup/>
</Response>"""
        return Response(response, mimetype="text/xml")


@app.route("/team", methods=["POST"])
def team():
    """Handle option 3 - Divert call to team number"""
    print("📞 Diverting call to team: 048966156")

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Please hold while I connect you to our team.
    </Say>
    <Dial>+6448873334</Dial>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/email_support", methods=["POST"])
def email_support():
    """Handle option 4 - Email support information"""
    print("📧 Providing email support information")

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        If you’d like to make a complaint or report a lost item, please email us at kiwi.cabs@xtra.co.nz.
        That's k-i-w-i dot c-a-b-s at x-t-r-a dot c-o dot n-z.
        We’ll be happy to help and get back to you as quickly as we can.
    </Say>
    <Hangup/>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/modification_menu", methods=["POST"])
def modification_menu():
    """Handle modification menu selection"""
    digits = request.form.get("Digits", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    print(f"📞 Modification menu selection: {digits}")

    # Store the selection in session for later use
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {}
    user_sessions[call_sid]["modification_type"] = digits

    if digits == "1":
        return redirect_to("/modify_time")
    elif digits == "2":
        return redirect_to("/modify_pickup")
    elif digits == "3":
        return redirect_to("/modify_destination")
    elif digits == "4":
        return redirect_to("/cancel_booking")
    else:
        return redirect_to("/modify_booking")


@app.route("/modify_time", methods=["POST"])
def modify_time():
    """Handle time modification"""
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        What time would you like to change your booking to?
        You can say things like "now", "in 30 minutes", "at 3 PM", or "tomorrow morning".
    </Say>
    <Gather input="speech" action="/process_time_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me the new time.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/modify_pickup", methods=["POST"])
def modify_pickup():
    """Handle pickup location modification"""
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        What is your new pickup address?
        For example, unit 1 at 27 melrose road.
    </Say>
    <Gather input="speech" action="/process_pickup_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me your new pickup address.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/modify_destination", methods=["POST"])
def modify_destination():
    """Handle destination modification"""
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        What is your new destination?
        You can say an address or a place name like Wellington Hospital.
    </Say>
    <Gather input="speech" action="/process_destination_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me your new destination.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/process_time_modification", methods=["POST"])
def process_time_modification():
    """Process time modification using AI"""
    speech_result = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    print(f"📝 Time modification request: '{speech_result}'")

    # Get original booking from session
    session_data = user_sessions.get(call_sid, {})
    original_booking = session_data.get("modifying_booking", {})

    if not original_booking:
        return redirect_to("/modify_booking")

    # Use the same time extraction logic as booking creation
    try:
        parsed_time = extract_time_with_ai(speech_result)
        print(f"parsed time:{parsed_time}")

        if parsed_time and parsed_time.get("pickup_time") and parsed_time.get("pickup_date"):
            # Update booking with new time
            updated_booking = original_booking.copy()
            updated_booking["pickup_time"] = parsed_time["pickup_time"]
            updated_booking["pickup_date"] = parsed_time["pickup_date"]

            # Format time for speech (same as booking creation)
            if parsed_time["pickup_time"] == "ASAP":
                time_string = "right now"
            else:
                formatted_time = format_time_for_speech(parsed_time["pickup_time"])
                if parsed_time["pickup_date"] == datetime.now(NZ_TZ).strftime("%d/%m/%Y"):
                    time_string = f"today at {formatted_time}"
                else:
                    time_string = f"on {parsed_time['pickup_date']} at {formatted_time}"

            # Save updated booking
            update_booking_to_db(caller_number, updated_booking)

            # Start background thread for TaxiCaller update
            threading.Thread(
                target=background_time_modification,
                args=(caller_number, updated_booking, original_booking, time_string),
                daemon=True
            ).start()

            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I've updated your time to {time_string}.
        We'll update your booking immediately.
        We appreciate your booking with Kiwi Cabs. Have a great day.
    </Say>
    <Hangup/>
</Response>"""
            return Response(response, mimetype="text/xml")
        elif parsed_time is None:
            # Handle case where time is in the past (same as booking creation)
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        That time is in the past. Would you like to pick a different time?
    </Say>
    <Gather input="speech" action="/process_time_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me the new time.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
            return Response(response, mimetype="text/xml")
        else:
            # Handle case where time couldn't be understood (same as booking creation)
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't understand the time. Could you please tell me when you need the taxi?
        For example, say "now", "in 30 minutes", or "at 3 PM".
    </Say>
    <Gather input="speech" action="/process_time_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me the new time.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
            return Response(response, mimetype="text/xml")

    except Exception as e:
        print(f"❌ Error processing time modification: {e}")
        return redirect_to("/modify_booking")


@app.route("/process_pickup_modification", methods=["POST"])
def process_pickup_modification():
    """Process pickup modification using existing logic"""
    speech_result = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    print(f"📝 Pickup modification request: '{speech_result}'")

    # Get original booking from session
    session_data = user_sessions.get(call_sid, {})
    original_booking = session_data.get("modifying_booking", {})

    if not original_booking:
        return redirect_to("/modify_booking")

    # Parse address to get clean and full versions
    try:
        clean_address, full_address = parse_address(speech_result)
        print(f"📍 Parsed pickup - Clean: {clean_address}, Full: {full_address}")

        # Use full address for POI resolution
        address_to_resolve = full_address if full_address else speech_result
        resolved_pickup = resolve_wellington_poi_to_address(address_to_resolve)

        if(resolved_pickup == False):
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Address not recognized. Could you please tell me your new pickup address again?
    </Say>
    <Gather input="speech" action="/process_pickup_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
            return Response(response, mimetype="text/xml")

        # Get the actual address string for storage and clean address for speech
        if isinstance(resolved_pickup, dict):
            exact_address = resolved_pickup.get("full_address", address_to_resolve)
            speech_address = clean_address if clean_address else resolved_pickup.get("speech", exact_address)
        else:
            exact_address = resolved_pickup if resolved_pickup else address_to_resolve
            speech_address = clean_address if clean_address else clean_address_for_speech(exact_address)

        # Update booking
        updated_booking = original_booking.copy()
        updated_booking["pickup_address"] = exact_address
        updated_booking["pickup_address_clean"] = speech_address

        # Save updated booking
        update_booking_to_db(caller_number, updated_booking)

        # Start background thread
        threading.Thread(
            target=background_pickup_modification,
            args=(caller_number, updated_booking, original_booking),
            daemon=True
        ).start()

        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I've updated your pickup to {speech_address}.
        We'll update your booking immediately.
        We appreciate your booking with Kiwi Cabs. Have a great day.
    </Say>
    <Hangup/>
</Response>"""
        return Response(response, mimetype="text/xml")

    except Exception as e:
        print(f"❌ Error processing pickup modification: {e}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't catch that. Could you please tell me your new pickup address?
    </Say>
    <Gather input="speech" action="/process_pickup_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me your new pickup address.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
        return Response(response, mimetype="text/xml")


@app.route("/process_destination_modification", methods=["POST"])
def process_destination_modification():
    """Process destination modification using existing logic"""
    speech_result = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    print(f"📝 Destination modification request: '{speech_result}'")

    # Get original booking from session
    session_data = user_sessions.get(call_sid, {})
    original_booking = session_data.get("modifying_booking", {})

    if not original_booking:
        return redirect_to("/modify_booking")

    # Parse address to get clean and full versions
    try:
        clean_address, full_address = parse_address(speech_result)
        print(f"📍 Parsed destination - Clean: {clean_address}, Full: {full_address}")

        # Use full address for POI resolution
        address_to_resolve = full_address if full_address else speech_result
        resolved_destination = resolve_wellington_poi_to_address(address_to_resolve)

        if(resolved_destination == False):
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Address not recognized. Could you please tell me your new destination again?
    </Say>
    <Gather input="speech" action="/process_destination_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">I am listening.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
            return Response(response, mimetype="text/xml")

        # Get the actual address string for storage and clean address for speech
        if isinstance(resolved_destination, dict):
            exact_address = resolved_destination.get("full_address", address_to_resolve)
            speech_address = clean_address if clean_address else resolved_destination.get("speech", exact_address)
        else:
            exact_address = resolved_destination if resolved_destination else address_to_resolve
            speech_address = clean_address if clean_address else clean_address_for_speech(exact_address)

        # Update booking
        updated_booking = original_booking.copy()
        updated_booking["destination"] = exact_address
        updated_booking["destination_clean"] = speech_address

        # Save updated booking
        update_booking_to_db(caller_number, updated_booking)

        # Start background thread
        threading.Thread(
            target=background_destination_modification,
            args=(caller_number, updated_booking, original_booking),
            daemon=True
        ).start()

        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I've updated your destination to {speech_address}.
        We'll update your booking immediately.
        We appreciate your booking with Kiwi Cabs. Have a great day.
    </Say>
    <Hangup/>
</Response>"""
        return Response(response, mimetype="text/xml")

    except Exception as e:
        print(f"❌ Error processing destination modification: {e}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't catch that. Could you please tell me your new destination?
    </Say>
    <Gather input="speech" action="/process_destination_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me your new destination.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
        return Response(response, mimetype="text/xml")


@app.route("/cancel_booking", methods=["POST"])
def cancel_booking():
    """Cancel booking confirmation"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Just to confirm - you want to cancel your taxi booking?
    </Say>
    <Gather action="/confirm_cancellation" input="speech" method="POST" timeout="10" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Say yes to cancel, or no to keep it.</Say>
    </Gather>
    <Redirect>/modify_booking</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/confirm_cancellation", methods=["POST"])
def confirm_cancellation():
    """Process cancellation confirmation"""
    speech_result = request.form.get("SpeechResult", "").lower()
    caller_number = request.form.get("From", "")
    response = ""

    if any(word in speech_result for word in ["yes", "confirm", "cancel", "yeah"]):
        # Cancel booking
        if caller_number in booking_storage:
            booking_storage[caller_number]["status"] = "cancelled"
            booking_storage[caller_number]["cancelled_at"] = datetime.now(NZ_TZ).isoformat()

            # Send cancellation to API
            cancelled_booking = booking_storage[caller_number].copy()
            cancelled_booking["status"] = "cancelled"
            # send_booking_to_api(cancelled_booking, caller_number)

            # Get order ID for TaxiCaller cancellation
            order_id = cancelled_booking.get('taxicaller_order_id')
            if order_id:
                # Cancel in TaxiCaller
                cancel_success = cancel_taxicaller_booking(order_id, cancelled_booking)
                if cancel_success:
                    # Update database
                    conn = get_db_connection()
                    if conn:
                        try:
                            cur = conn.cursor()
                            cur.execute(
                                "UPDATE bookings SET status = 'cancelled' WHERE customer_phone = %s AND status = 'confirmed'",
                                (caller_number,)
                            )
                            conn.commit()
                            cur.close()
                            conn.close()
                        except Exception as e:
                            print(f"❌ Database update error: {e}")
                            if conn:
                                conn.close()
                
                response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! I've cancelled your booking. Thanks for letting us know!
    </Say>
    <Hangup/>
</Response>"""
            else:
                response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I've recorded your cancellation. Your booking has been cancelled.
    </Say>
    <Hangup/>
</Response>"""
        else:
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I couldn't find a booking to cancel.
    </Say>
    <Redirect>/modify_booking</Redirect>
</Response>"""
    else:
        # Customer said no
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Okay, I won't cancel your booking.
    </Say>
    <Redirect>/modify_booking</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")
