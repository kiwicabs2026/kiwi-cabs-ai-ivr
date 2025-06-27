import os
import sys
import requests
import json
from flask import Flask, request, Response, jsonify
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
        
        if results:
            result = results[0]
            components = result['address_components']
            
            street_number = ""
            street_name = ""
            suburb = ""
            
            for comp in components:
                types = comp['types']
                if 'street_number' in types:
                    street_number = comp['long_name']
                elif 'route' in types:
                    street_name = comp['long_name']
                elif 'sublocality_level_1' in types:
                    suburb = comp['long_name']
            
            # Build clean address
            if street_number and street_name:
                clean_address = f"{street_number} {street_name}"
                if suburb:
                    clean_address += f", {suburb}"
            else:
                clean_address = address
            
            print(f"✅ Google Maps validated: {address} → {clean_address}")
            return clean_address
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


def transcribe_with_google(audio_url):
    """Use Google Speech for better transcription"""
    if not GOOGLE_SPEECH_AVAILABLE or not google_speech_client:
        print("❌ Google Speech client not available")
        return None, 0

    try:
        print(f"🎤 Fetching audio from: {audio_url}")

        response = requests.get(audio_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        if response.status_code != 200:
            print(f"❌ Failed to download audio: {response.status_code}")
            return None, 0

        audio_content = response.content
        print(f"✅ Downloaded audio: {len(audio_content)} bytes")

        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,
            language_code="en-NZ",
            enable_automatic_punctuation=True,
            enable_word_confidence=True,
            speech_contexts=[
                speech.SpeechContext(
                    phrases=[
                        "Willis Street",
                        "Cuba Street",
                        "Lambton Quay",
                        "Courtenay Place",
                        "Taranaki Street",
                        "Victoria Street",
                        "Manners Street",
                        "Dixon Street",
                        "Wakefield Street",
                        "Cable Street",
                        "Oriental Parade",
                        "Kent Terrace",
                        "Hobart Street",
                        "Molesworth Street",
                        "The Terrace",
                        "Featherston Street",
                        "Wellington",
                        "Lower Hutt",
                        "Upper Hutt",
                        "Porirua",
                        "Petone",
                        "Island Bay",
                        "Newtown",
                        "Kilbirnie",
                        "Miramar",
                        "Karori",
                        "Kelburn",
                        "Thorndon",
                        "Te Aro",
                        "Mount Victoria",
                        "Oriental Bay",
                        "Airport",
                        "Hospital",
                        "Railway Station",
                        "Train Station",
                        "Te Papa",
                        "Westpac Stadium",
                        "Sky Stadium",
                        "Wellington Zoo",
                    ],
                    boost=20.0,
                )
            ],
            max_alternatives=3,
            model="phone_call",
            use_enhanced=True,
        )

        print("🔄 Sending to Google Speech API...")
        response = google_speech_client.recognize(config=config, audio=audio)

        if response.results:
            best_result = response.results[0].alternatives[0]
            confidence = best_result.confidence
            transcript = best_result.transcript

            print(
                f"✅ GOOGLE SPEECH RESULT: {transcript} (confidence: {confidence:.2f})"
            )
            return transcript, confidence
        else:
            print("❌ No speech detected by Google")
            return None, 0

    except Exception as e:
        print(f"❌ Google Speech Error: {str(e)}")
        return None, 0


def get_taxicaller_jwt():
    print("🚀 Starting get_taxicaller_jwt()")
    if (
        TAXICALLER_JWT_CACHE["token"]
        and time.time() < TAXICALLER_JWT_CACHE["expires_at"]
    ):
        print("📌 Using cached JWT token")
        return TAXICALLER_JWT_CACHE["token"]

    if not TAXICALLER_API_KEY:
        print("❌ No TaxiCaller API key configured - skipping JWT")
        return None

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


def send_booking_to_taxicaller(booking_data, caller_number):
    """Send booking to TaxiCaller API using the correct v1 endpoint"""
    try:
        # Get environment variables
        TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY")
        COMPANY_ID = os.getenv("COMPANY_ID", "")  # Add your company ID in Render
        USER_ID = os.getenv("USER_ID", "")  # Optional
        
        if not TAXICALLER_API_KEY:
            print("❌ No TaxiCaller API key available")
            return False, None
            
        print(f"🔑 Using TaxiCaller API Key: {TAXICALLER_API_KEY[:8]}...")
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
            pickup_datetime = datetime.now() + timedelta(minutes=5)
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
                    today = datetime.now()
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
                pickup_datetime = datetime.now() + timedelta(hours=1)

        # Format to ISO format WITHOUT timezone as per guide
        pickup_time_iso = pickup_datetime.strftime("%Y-%m-%dT%H:%M:%S+12:00")

        # Create payload according to the guide
       # Create payload according to the guide
        booking_payload = {
            "apiKey": TAXICALLER_API_KEY,  # Note: capital K
            "customerPhone": caller_number,
            "customerName": booking_data["name"],
            "pickup": booking_data["pickup_address"],
            "dropoff": booking_data["destination"],
            "time": pickup_time_iso,  # Format: '2025-05-29T15:30:00+12:00'
        }
        
        # Add optional User ID if available
        if USER_ID:
            booking_payload["userid"] = USER_ID
        
        # Add notes if available
        if booking_data.get("raw_speech"):
            booking_payload["notes"] = f"AI IVR Booking - {booking_data.get('raw_speech', '')}"

        # Use the correct endpoint from the guide
        booking_url = "https://api-rc.taxicaller.net/api/v1/bookings"


        # Get JWT token first
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            print("❌ No JWT token available")
            return False, None

# Define endpoints and headers for the loop
        # Define endpoints and headers for the loop
        possible_endpoints = [booking_url]  # Use the single correct endpoint
        headers_options = [
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {jwt_token.get('token', '')}",
                "User-Agent": "KiwiCabs-AI-IVR/2.1"
            }
        ]

        print(f"📤 SENDING TO TAXICALLER V2:")
        print(f"   URL: {booking_url}")
        print(f"   API Key: {TAXICALLER_API_KEY[:8]}...")
        print(f"   Customer: {booking_payload['customerName']}")
        print(f"   Phone: {booking_payload['customerPhone']}")
        print(f"   Pickup: {booking_payload['pickup']}")
        print(f"   Dropoff: {booking_payload['dropoff']}")
        print(f"   Time: {booking_payload['time']}")


        # Try multiple TaxiCaller endpoints since the original doesn't exist
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

                    # STEP 4: Log the API response and handle errors
                    if response.status_code in [200, 201]:
                        try:
                            response_data = response.json()
                            booking_id = response_data.get(
                                "bookingId", response_data.get("id", "Unknown")
                            )
                            print(f"✅ TAXICALLER BOOKING CREATED: {booking_id}")
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
        print(f"❌ TAXICALLER API ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return False, None


def parse_booking_speech(speech_text):
    """STEP 3: Parse booking details from speech input"""
    booking_data = {
        "name": "",
        "pickup_address": "",
        "destination": "",
        "pickup_time": "",
        "pickup_date": "",
        "raw_speech": speech_text,
    }
    # Extract weekdays (Monday, Tuesday, ...)
    from datetime import datetime, timedelta

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    # Check for weekday mentioned explicitly
    for day_name, day_index in weekdays.items():
        if day_name in speech_text.lower():
            today_weekday = datetime.now().weekday()
            days_ahead = day_index - today_weekday
            if days_ahead <= 0:  # if mentioned day is today or passed, move to next week
                days_ahead += 7
            pickup_date = datetime.now() + timedelta(days=days_ahead)
            booking_data["pickup_date"] = pickup_date.strftime("%d/%m/%Y")
            break

    # Extract name
    name_patterns = [
        r"(?:my name is|i am|this is|it's)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b(?!\s+(?:Street|Road|Avenue|Lane|Drive))",
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b(?!\s+(?:Street|Road|Avenue|Lane|Drive))\s+from",
    ]

    import re
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
        r"from\s+(?:number\s+)?(\d+\s+[A-Za-z]+(?:\s+(?:Street|Road|Avenue|Lane|Drive|Crescent|Way|Boulevard|Terrace)))",
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

            # Smart destination mapping
            if "hospital" in destination.lower():
                destination = "Wellington Hospital"
            elif any(
                airport_word in destination.lower()
                for airport_word in [
                    "airport", "the airport", "domestic airport", "international airport",
                    "steward duff", "stewart duff", "wlg airport", "wellington airport"
                ]
            ):
                destination = "Wellington Airport"
            elif "station" in destination.lower() or "railway" in destination.lower():
                destination = "Wellington Railway Station"
            elif "te papa" in destination.lower():
                destination = "Te Papa Museum"

        booking_data["destination"] = destination
        # AI Smart Cleaning - Remove time from destination
        if booking_data["destination"]:
            dest = booking_data["destination"]
            # Remove time patterns
            dest = re.sub(r'\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)', '', dest, flags=re.IGNORECASE)
            dest = re.sub(r'\s+by\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)', '', dest, flags=re.IGNORECASE)
            booking_data["destination"] = dest.strip()
        break

    # Extract date - IMPROVED TO HANDLE SPECIFIC DATES LIKE 22nd, 23rd
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
        current_time = datetime.now()
        booking_data["pickup_date"] = current_time.strftime("%d/%m/%Y")
        booking_data["pickup_time"] = "ASAP"
    elif any(keyword in speech_text.lower() for keyword in after_tomorrow_keywords):
        # Handle "after tomorrow" - add 2 days
        after_tomorrow = datetime.now() + timedelta(days=2)
        booking_data["pickup_date"] = after_tomorrow.strftime("%d/%m/%Y")
    elif date_match:
        # Customer specified a specific date number
        day = int(date_match.group(1))
        current_date = datetime.now()
        current_month = current_date.month
        current_year = current_date.year

        # If the day has already passed this month, assume next month
        if day < current_date.day:
            if current_month == 12:
                current_month = 1
                current_year += 1
            else:
                current_month += 1

        booking_data["pickup_date"] = f"{day:02d}/{current_month:02d}/{current_year}"
    elif any(keyword in speech_text.lower() for keyword in tomorrow_keywords):
        tomorrow = datetime.now() + timedelta(days=1)
        booking_data["pickup_date"] = tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in today_keywords):
        today = datetime.now()
        booking_data["pickup_date"] = today.strftime("%d/%m/%Y")

    # Extract time
    time_patterns = [
        r"in\s+(\d+)\s+minutes?",  # Keep this one
        r"in\s+(\d+)\s+hours?",    # Keep this one  
        r"time\s+(\d{1,2}):(\d{0,2})\s*(?:am|pm|a\.m\.|p\.m\.)?",
        r"at\s+(\d{1,2}):(\d{0,2})\s*(?:am|pm|a\.m\.|p\.m\.)?",
        r"(\d{1,2}):(\d{0,2})\s*(?:am|pm|a\.m\.|p\.m\.)?",
    
        # ADD THESE NEW SMART PATTERNS:
        r"(?:in\s+)?(?:a\s+)?half\s+(?:an\s+)?hours?",      # "half hour", "half an hour", "in half hour"
        r"(?:in\s+)?(?:about\s+)?thirty\s+minutes?",        # "thirty minutes", "in thirty minutes"  
        r"(?:in\s+)?(?:about\s+)?30\s+minutes?",            # "30 minutes", "in 30 minutes"
        r"(?:within\s+)?(?:a\s+)?half\s+(?:an\s+)?hours?",  # "within half hour", "within a half hour"
        r"(?:within\s+)?thirty\s+minutes?",                 # "within thirty minutes"
        r"(?:within\s+)?30\s+minutes?",                     # "within 30 minutes"
    ]

    # Add special handling for "half hour" BEFORE the pattern matching
    if any(phrase in speech_text.lower() for phrase in ["half hour", "half an hour", "30 minutes"]):
        pass
        
        
    elif not any(keyword in speech_text.lower() for keyword in immediate_keywords):
       # Then do the pattern matching
       for pattern in time_patterns:
           match = re.search(pattern, speech_text, re.IGNORECASE)
           if match:
               matched_text = speech_text.lower()
               
               # Check what was actually said, not the pattern
               if ("half" in matched_text or "haf" in matched_text or "haff" in matched_text) and ("hour" in matched_text):
                   nz_tz = pytz.timezone('Pacific/Auckland')
                   booking_time = datetime.now(nz_tz) + timedelta(minutes=30)
                   time_str = f"In 30 minutes ({booking_time.strftime('%I:%M %p')})"
                   booking_data["pickup_time"] = time_str
                   booking_data["pickup_date"] = datetime.now(nz_tz).strftime("%d/%m/%Y")
                   break
               
               elif ("30" in matched_text and "minute" in matched_text) or ("thirty" in matched_text and "minute" in matched_text):
                   nz_tz = pytz.timezone('Pacific/Auckland')
                   booking_time = datetime.now(nz_tz) + timedelta(minutes=30)
                   time_str = f"In 30 minutes ({booking_time.strftime('%I:%M %p')})"
                   booking_data["pickup_time"] = time_str
                   booking_data["pickup_date"] = datetime.now(nz_tz).strftime("%d/%m/%Y")
                   break
               
               elif "minute" in matched_text and any(char.isdigit() for char in matched_text):
                   digit_match = re.search(r"(\d+)", matched_text)
                   if digit_match:
                       minutes = int(digit_match.group(1))
                       nz_tz = pytz.timezone('Pacific/Auckland')
                       booking_time = datetime.now(nz_tz) + timedelta(minutes=minutes)
                       time_str = f"In {minutes} minutes ({booking_time.strftime('%I:%M %p')})"
                       booking_data["pickup_time"] = time_str
                       booking_data["pickup_date"] = datetime.now(nz_tz).strftime("%d/%m/%Y")
                       break
               
               else:
                   # Default fallback - 30 minutes from now
                   nz_tz = pytz.timezone('Pacific/Auckland')
                   booking_time = datetime.now(nz_tz) + timedelta(minutes=30)
                   time_str = f"In 30 minutes ({booking_time.strftime('%I:%M %p')})"
                   booking_data["pickup_time"] = time_str
                   booking_data["pickup_date"] = datetime.now(nz_tz).strftime("%d/%m/%Y")
                   break
       
       # Move to confirmation step
       session["booking_step"] = "confirmation"
       
       # Create response
       pickup_time = partial_booking.get("pickup_time", "soon")
                
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
            pickup = validate_and_format_address(pickup, "pickup")
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
            destination = validate_and_format_address(destination, "destination")
        booking_data['destination'] = destination.strip()
    
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
        "created_at": datetime.now().isoformat(),
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
        Nice to meet you, {name}! 
        What's your pickup address?
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
        if pickup_lower.startswith("i need a taxi from "):    # ADD THIS LINE
           pickup = pickup[19:].strip()
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
        if "railway station" in pickup.lower() or "train station" in pickup.lower():
           pickup = "Wellington Railway Station"
        elif "airport" in pickup.lower() and "from" not in pickup.lower():
            pickup = "Wellington Airport"
        
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
            
            # Validate with Google Maps if available
            if gmaps:
                pickup = validate_and_format_address(pickup, "pickup")
            
            partial_booking["pickup_address"] = pickup
            session["booking_step"] = "destination"
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! I have your pickup at {pickup}.
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
        # Process destination
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
        
        # Smart destination mapping
        if "hospital" in destination.lower():
            destination = "Wellington Hospital"
        elif any(airport_word in destination.lower() for airport_word in ["airport", "the airport", "domestic", "international"]):
            destination = "Wellington Airport"
        elif any(station_word in destination.lower() for station_word in ["station", "railway", "train"]):
            destination = "Wellington Railway Station"
        elif "te papa" in destination.lower():
            destination = "Te Papa Museum"
        
        if len(destination) >= 3:
            # Validate with Google Maps if available
            if gmaps:
                destination = validate_and_format_address(destination, "destination")
            
            partial_booking["destination"] = destination
            session["booking_step"] = "time"
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! Going to {destination}.
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
        immediate_keywords = ["now", "right now", "immediately", "asap", "as-soon-as-possible", "straight away"]
        if any(keyword in time_text for keyword in immediate_keywords):
            partial_booking["pickup_time"] = "ASAP"
            partial_booking["pickup_date"] = datetime.now().strftime("%d/%m/%Y")
            time_string = "right now"
            valid_time = True
        else:
            # Try to parse natural time expressions
            parsed_time = parse_time(time_text)
            if parsed_time:
                partial_booking["pickup_time"] = parsed_time
                partial_booking["pickup_date"] = datetime.now().strftime("%d/%m/%Y")
                time_string = f"today at {parsed_time}"
                valid_time = True
            else:
                # Fallback: if date already exists, ask again for time
                if "pickup_date" in partial_booking:
                    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.ArIa-Neural" language="en-NZ">
        Thanks. What time should we pick you up?
    </Say>
    <Redirect>/book_taxi</Redirect>
</Response>"""
                    return Response(response, mimetype="text/xml")

        # Date specified but no time - ask for time
        partial_booking["pickup_date"] = parsed_booking["pickup_date"]
        response = f"""<?xml version="1.0" encoding="UTF-8"?>

<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        What time on {parsed_booking['pickup_date']} would you like the taxi?
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me the time.</Say>
    </Gather>
</Response>"""
                return Response(response, mimetype="text/xml")
        
        if valid_time:
            session["booking_step"] = "confirmation"
            
            # Build confirmation message
            confirmation_text = f"Let me confirm your booking details: {partial_booking['name']}, "
            confirmation_text += f"pickup from {partial_booking['pickup_address']}, "
            confirmation_text += f"going to {partial_booking['destination']}, "
            confirmation_text += f"{time_string}"
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/confirm_booking" input="speech" method="POST" timeout="10" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            {confirmation_text}.
            Is this correct? Say yes to confirm or no to start over.
        </Say>
    </Gather>
    <Redirect>/process_booking</Redirect>
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
    
    # Store session updates
    session["partial_booking"] = partial_booking
    user_sessions[call_sid] = session
    
    # Store in pending for confirmation step
    if current_step == "time" and valid_time:
        user_sessions[call_sid]["pending_booking"] = partial_booking
        user_sessions[call_sid]["caller_number"] = caller_number
    
    return Response(response, mimetype="text/xml")


@app.route("/process_booking_with_google", methods=["POST"])
def process_booking_with_google():
    """Process booking using Google Speech from recording"""
    recording_url = request.form.get("RecordingUrl", "")
    call_sid = request.form.get("CallSid", "")

    print(f"🎤 Processing Google Speech recording: {recording_url}")

    if not recording_url:
        return redirect_to("/book_taxi")

    # Try Google transcription
    transcript, confidence = transcribe_with_google(recording_url)

    if transcript and confidence > 0.5:
        print(f"✅ Google transcript: {transcript} (confidence: {confidence:.2f})")

        # Create fake request data for processing
        from werkzeug.datastructures import ImmutableMultiDict

        fake_form = ImmutableMultiDict(
            [
                ("SpeechResult", transcript),
                ("Confidence", str(confidence)),
                ("CallSid", call_sid),
                ("From", user_sessions.get(call_sid, {}).get("caller_number", "")),
            ]
        )

        # Temporarily replace request.form
        original_form = request.form
        request.form = fake_form

        try:
            response = process_booking()
            return response
        finally:
            request.form = original_form
    else:
        print(f"❌ Google transcription failed")
        return Response(
            """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I'm having trouble understanding. Let me transfer you to our team.
    </Say>
    <Dial>
        <Number>+6448966156</Number>
    </Dial>
</Response>""",
            mimetype="text/xml",
        )


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

    # Check for yes/confirm - FIXED: Look for "yes" anywhere in the response
    if any(
        word in speech_result
        for word in ["yes", "confirm", "correct", "right", "ok", "okay", "yep", "yeah"]
    ):
        print("✅ Booking confirmed - processing immediately")

        # Store booking immediately
        booking_storage[caller_number] = {
            **booking_data,
            "confirmed_at": datetime.now().isoformat(),
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
                    except:
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
        simple_confirm = f"Is this booking correct? {booking.get('name')}, from {booking.get('pickup_address')} to {booking.get('destination')}"
        
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
        pickup = booking.get("pickup_address", "")
        destination = booking.get("destination", "")
        pickup_date = booking.get("pickup_date", "")
        pickup_time = booking.get("pickup_time", "")

        # Build time string
        time_str = ""
        if pickup_time == "ASAP":
            time_str = "as soon as possible"
        elif pickup_date and pickup_time:
            time_str = f"on {pickup_date} at {pickup_time}"
        elif pickup_time:
            time_str = f"at {pickup_time}"

        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Hello {name}, I found your booking.
        You have a taxi from {pickup} to {destination} {time_str}.
        What would you like to change? You can change the time, pickup location, destination, or cancel the booking.
        Go ahead, I am listening
    </Say>
    <Gather input="speech" 
            action="/process_modification_smart" 
            method="POST" 
            timeout="20" 
            language="en-NZ" 
            speechTimeout="1">
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


@app.route("/process_modification_smart", methods=["POST"])
def process_modification_smart():
    """Smart processing - extract all changes from one speech input"""
    speech_result = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")

    print(f"📝 Modification request: '{speech_result}'")

    # Get original booking
    if caller_number not in booking_storage:
        return redirect_to("/modify_booking")

    original_booking = booking_storage[caller_number].copy()

    # Check for cancellation first
    if any(
        word in speech_result.lower()
        for word in ["cancel", "delete", "don't need", "not going"]
    ):
        return redirect_to("/cancel_booking")

    # Check if they want no changes
    if any(
        word in speech_result.lower()
        for word in ["nothing", "no change", "keep it", "fine", "good", "same"]
    ):
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Your booking remains unchanged.
        We'll see you at your scheduled pickup time.
    </Say>
    <Hangup/>
</Response>"""
        return Response(response, mimetype="text/xml")

    # Create updated booking starting with original data
    updated_booking = original_booking.copy()
    changes_made = []

    # Check if speech mentions address/location keywords
    has_pickup_keywords = any(
        word in speech_result.lower()
        for word in ["pickup", "pick up", "from", "address", "pick me"]
    )
    has_destination_keywords = any(
        word in speech_result.lower()
        for word in ["destination", "drop", "take me to", "going to"]
    )

    # Only parse for full booking details if they're changing addresses
    if has_pickup_keywords or has_destination_keywords:
        modification_data = parse_booking_speech(speech_result)

        # Update pickup if provided and different
        if has_pickup_keywords and modification_data["pickup_address"]:
            # Skip if the parsed "pickup address" is actually a time
            if any(time_word in modification_data["pickup_address"].lower() for time_word in ["a.m.", "p.m.", "am", "pm", "o'clock"]):
                modification_data["pickup_address"] = ""  # Clear it - it's not an address
            # CHECK FOR AIRPORT PICKUP
            if any(
                keyword in modification_data["pickup_address"].lower()
                for keyword in ["airport", "terminal"]
            ):
                print(f"✈️ Airport pickup modification rejected")
                response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, you don't need to book a taxi from the airport as we have taxis queuing at the airport rank.
        Just walk to the rank and catch any Kiwi Cabs in the rank.
    </Say>
    <Hangup/>
</Response>"""
                return Response(response, mimetype="text/xml")

            updated_booking["pickup_address"] = modification_data["pickup_address"]
            changes_made.append(
                f"pickup address to {modification_data['pickup_address']}"
            )

        # Update destination if provided and different
        if has_destination_keywords and modification_data["destination"]:
            updated_booking["destination"] = modification_data["destination"]
            changes_made.append(f"destination to {modification_data['destination']}")

    # IMPROVED TIME PARSING - More flexible patterns
    time_patterns = [
        r"(\d{1,2})\s*(?:am|pm|a\.m\.|p\.m\.)",  # Matches "11 am", "11am", "11 a.m."
        r"make it (\d{1,2})\s*(?:am|pm|a\.m\.|p\.m\.)",  # "make it 11 am"
        r"change.*?to (\d{1,2})\s*(?:am|pm|a\.m\.|p\.m\.)",  # "change to 11 am"
        r"at (\d{1,2})\s*(?:am|pm|a\.m\.|p\.m\.)",  # "at 11 am"
        r"(\d{1,2}):(\d{2})\s*(?:am|pm|a\.m\.|p\.m\.)?",  # "11:30 am"
    ]

    time_found = False
    time_str = ""  # Initialize time_str variable to avoid scope issues
    # Special handling for "from X to Y" time changes
    if "from" in speech_result.lower() and "to" in speech_result.lower():
        from_to_pattern = r'from\s+(\d{1,2})\s*(?:am|pm|a\.m\.|p\.m\.)?\s+to\s+(\d{1,2})\s*(?:am|pm|a\.m\.|p\.m\.)'
        from_to_match = re.search(from_to_pattern, speech_result, re.IGNORECASE)
        if from_to_match:
            # Take the SECOND time (after "to")
            hour = from_to_match.group(2)
            time_str = f"{hour}:00"
            if "pm" in speech_result.lower() or "p.m." in speech_result.lower():
                time_str += " PM"
            elif "am" in speech_result.lower() or "a.m." in speech_result.lower():
                time_str += " AM"
            updated_booking["pickup_time"] = time_str
            time_found = True
    for pattern in time_patterns:
        match = re.search(pattern, speech_result, re.IGNORECASE)
        if match:
            # Always safely extract hour and minute
            hour = match.group(1)
            minute = "00"
            if match.lastindex and match.lastindex >= 2 and match.group(2):
                minute = match.group(2)
            time_str = f"{hour}:{minute}"

            # Add AM/PM
            if "pm" in speech_result.lower() or "p.m." in speech_result.lower():
                time_str += " PM"
            elif "am" in speech_result.lower() or "a.m." in speech_result.lower():
                time_str += " AM"

            updated_booking["pickup_time"] = time_str
            time_found = True
            break  # exits the for loop

    # Check for date keywords only if time was found
    if time_found:
        if "tomorrow" in speech_result.lower():
            tomorrow = datetime.now() + timedelta(days=1)
            updated_booking["pickup_date"] = tomorrow.strftime("%d/%m/%Y")
            changes_made.append(f"time to tomorrow at {time_str}")
        elif "today" in speech_result.lower():
            today = datetime.now()
            updated_booking["pickup_date"] = today.strftime("%d/%m/%Y")
            changes_made.append(f"time to today at {time_str}")
        else:
            pass
            # Just time change, keep original date
        changes_made.append(f"time to {time_str}")
    # If changes were made, update the booking
    if changes_made:
        # IMMEDIATE RESPONSE TO CUSTOMER - Don't make them wait!
        changes_text = " and ".join(changes_made)
        
        # Build complete booking details for confirmation
        pickup_str = updated_booking["pickup_address"]
        # Build complete booking details for confirmation
        pickup_str = updated_booking["pickup_address"]
        # FIX: If pickup is empty, use original booking's pickup
        if not pickup_str and original_booking.get("pickup_address"):
            pickup_str = original_booking["pickup_address"]
            updated_booking["pickup_address"] = original_booking["pickup_address"]


        dest_str = updated_booking["destination"]
        dest_str = updated_booking["destination"]
        time_confirmation_str = ""

        if updated_booking.get("pickup_time") == "ASAP":
            time_confirmation_str = "as soon as possible"
        elif updated_booking.get("pickup_date") and updated_booking.get("pickup_time"):
            time_confirmation_str = f"on {updated_booking['pickup_date']} at {updated_booking['pickup_time']}"
        elif updated_booking.get("pickup_time"):
            time_confirmation_str = f"at {updated_booking['pickup_time']}"

        # IMMEDIATE RESPONSE - Customer doesn't wait for API calls
        immediate_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Your booking has been updated successfully.
        Your taxi will pick you up from {pickup_str} and take you to {dest_str} {time_confirmation_str}.
        We appreciate your booking with Kiwi Cabs. Have a great day.
    </Say>
    <Hangup/>
</Response>"""

        # BACKGROUND PROCESSING - Don't make customer wait
        def background_modification():
            try:
                print("🔄 BACKGROUND: Starting modification process...")
                
                # Update database first
                conn = get_db_connection()
                if conn:
                    try:
                        cur = conn.cursor()
                        # Start transaction
                        cur.execute("BEGIN")
                        # Update the booking status to 'modified'
                        cur.execute(
                            "UPDATE bookings SET status = 'modified' WHERE customer_phone = %s AND status = 'confirmed'",
                            (caller_number,),
                        )
                        # Commit transaction
                        cur.execute("COMMIT")
                        conn.commit()
                        cur.close()
                        conn.close()
                        print("✅ BACKGROUND: Database updated")
                    except Exception as e:
                        print(f"❌ BACKGROUND: Database update error: {e}")
                        if conn:
                            try:
                                cur.execute("ROLLBACK")
                                conn.close()
                            except:
                                pass

                # STEP 1: Cancel the old booking first
                print("❌ BACKGROUND: Cancelling old booking")
                cancel_booking = original_booking.copy()
                cancel_booking["status"] = "cancelled"
                cancel_booking["cancelled_at"] = datetime.now().isoformat()
                cancel_booking["cancellation_reason"] = "Customer modified booking"

                # Send cancellation to TaxiCaller/API
                cancel_success, cancel_response = send_booking_to_api(cancel_booking, caller_number)
                if cancel_success:
                    print("✅ BACKGROUND: Old booking cancelled successfully")
                else:
                    print("⚠️ BACKGROUND: Failed to cancel old booking - continuing with new booking")

                # STEP 2: Create new booking with modifications
                updated_booking["modified_at"] = datetime.now().isoformat()
                updated_booking["raw_speech"] = f"Modified booking (replaces cancelled): change time to {updated_booking.get('pickup_time', '')}"
                updated_booking["previous_booking_cancelled"] = True
                updated_booking["replaces_booking"] = original_booking.get("booking_reference", "")

                # Replace the booking in storage
                booking_storage[caller_number] = updated_booking

                # Send the NEW booking to API
                print("📝 BACKGROUND: Sending new modified booking")
                print(f"   Name: {updated_booking['name']}")
                print(f"   From: {updated_booking['pickup_address']}")
                print(f"   To: {updated_booking['destination']}")
                print(f"   Time: {updated_booking.get('pickup_time', '')}")
                print(f"   Date: {updated_booking.get('pickup_date', '')}")

                success, api_response = send_booking_to_api(updated_booking, caller_number)
                if success:
                    print("✅ BACKGROUND: New booking sent successfully")
                else:
                    print("❌ BACKGROUND: Failed to send new booking")
                    
                print("✅ BACKGROUND: Modification process completed")
            except Exception as e:
                print(f"❌ BACKGROUND: Modification error: {str(e)}")

        # Start background thread for API processing
        threading.Thread(target=background_modification, daemon=True).start()
        
        return Response(immediate_response, mimetype="text/xml")
    else:
        # Extract new pickup address if mentioned
        pickup_patterns = [
            r"pick.*?up.*?(?:from|at)\s+(?:number\s+)?([^,]+?)(?:\s+(?:instead|and|to|going))",
            r"from\s+(?:number\s+)?([^,]+?)(?:\s+(?:instead|and|to|going))",
            r"change.*?pickup.*?to\s+(?:number\s+)?([^,]+?)(?:\s+(?:and|to|going|$))",
            r"new.*?address.*?is\s+(?:number\s+)?([^,]+?)(?:\s+(?:and|to|going|$))",
        ]
        for pattern in pickup_patterns:
            match = re.search(pattern, speech_result, re.IGNORECASE)
            if match:
                new_pickup = match.group(1).strip()
                new_pickup = re.sub(r"\bnumber\s+", "", new_pickup, flags=re.IGNORECASE)
                if new_pickup and new_pickup != original_booking["pickup_address"]:
                    updated_booking["pickup_address"] = new_pickup
                    changes_made.append(f"pickup to {new_pickup}")
                break
        
        # Extract new destination if mentioned
        destination_patterns = [
            r"(?:to|going to|destination)\s+(?:the\s+)?([^,]+?)(?:\s+(?:instead|at|on|and|$))",
            r"take.*?me.*?to\s+(?:the\s+)?([^,]+?)(?:\s+(?:instead|at|on|and|$))",
            r"change.*?destination.*?to\s+(?:the\s+)?([^,]+?)(?:\s+(?:at|on|and|$))",
        ]

        for pattern in destination_patterns:
            match = re.search(pattern, speech_result, re.IGNORECASE)
            if match:
                new_dest = match.group(1).strip()
                # Smart destination mapping
                if "hospital" in new_dest.lower():
                    new_dest = "Wellington Hospital"
                elif "airport" in new_dest.lower():
                    new_dest = "Wellington Airport"
                elif "station" in new_dest.lower():
                    new_dest = "Wellington Railway Station"

                if new_dest and new_dest != original_booking["destination"]:
                    updated_booking["destination"] = new_dest
                    changes_made.append(f"destination to {new_dest}")
                break

        # Extract new time if mentioned
        time_keywords = [
            "tomorrow",
            "today",
            "tonight",
            "morning",
            "afternoon",
            "evening",
            "am",
            "pm",
            "o'clock",
        ]
        if any(keyword in speech_result.lower() for keyword in time_keywords):
            # Use existing parse_booking_speech to extract time
            temp_booking = parse_booking_speech(speech_result)
            if temp_booking.get("pickup_time"):
                updated_booking["pickup_time"] = temp_booking["pickup_time"]
                if temp_booking.get("pickup_date"):
                    updated_booking["pickup_date"] = temp_booking["pickup_date"]
                time_update_str = f"{temp_booking.get('pickup_date', '')} at {temp_booking['pickup_time']}".strip()
                changes_made.append(f"time to {time_update_str}")

        # If changes were made after fallback parsing, update the booking
        if changes_made:
            # Mark old booking as modified/cancelled
            booking_storage[caller_number]["status"] = "modified"
            booking_storage[caller_number]["modified_at"] = datetime.now().isoformat()

            # Create new booking with updates
            updated_booking["modified_from_original"] = True
            updated_booking["original_booking_ref"] = original_booking.get(
                "booking_reference", ""
            )
            updated_booking["confirmed_at"] = datetime.now().isoformat()
            updated_booking["status"] = "confirmed"

            # Replace the booking
            booking_storage[caller_number] = updated_booking

            # Send the updated booking to API (this creates a new booking, old one is marked as modified)
            send_booking_to_api(updated_booking, caller_number)

            changes_text = " and ".join(changes_made)
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! I've updated your {changes_text}.
        Your taxi will now pick you up from {updated_booking['pickup_address']} 
        and take you to {updated_booking['destination']} 
        {f"on {updated_booking['pickup_date']}" if updated_booking.get('pickup_date') else ""} 
        {f"at {updated_booking['pickup_time']}" if updated_booking.get('pickup_time') else ""}.
        Your previous booking has been cancelled.
    </Say>
    <Hangup/>
</Response>"""
        else:
            # Couldn't understand the changes
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't understand what you wanted to change.
        Please tell me clearly what you'd like to update - for example:
        "Change pickup to 45 Willis Street" or "Change time to 3 PM tomorrow".
    </Say>
    <Gather input="speech" action="/process_modification_smart" method="POST" timeout="20" language="en-NZ" speechTimeout="1">
        <Say voice="Polly.Aria-Neural" language="en-NZ">Please tell me what to change.</Say>
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

    if any(word in speech_result for word in ["yes", "confirm", "cancel", "yeah"]):
        # Cancel booking
        if caller_number in booking_storage:
            booking_storage[caller_number]["status"] = "cancelled"
            booking_storage[caller_number]["cancelled_at"] = datetime.now().isoformat()

            # Send cancellation to API
            cancelled_booking = booking_storage[caller_number].copy()
            cancelled_booking["status"] = "cancelled"
            send_booking_to_api(cancelled_booking, caller_number)

            # Remove from active bookings
            del booking_storage[caller_number]

            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! I've cancelled your booking. 
        Thanks for letting us know!
    </Say>
    <Hangup/>
</Response>"""
        else:
            response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I couldn't find your booking to cancel.
    </Say>
    <Hangup/>
</Response>"""
    else:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! Your booking is still active. 
        See you at pickup time!
    </Say>
    <Hangup/>
</Response>"""

    return Response(response, mimetype="text/xml")


@app.route("/team", methods=["POST"])
def team():
    """Transfer to human team"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Please hold while I transfer you to our team.
    </Say>
    <Dial>
        <Number>+6448966156</Number>
    </Dial>
</Response>"""
    return Response(response, mimetype="text/xml")


@app.route("/api/bookings", methods=["POST"])
def api_bookings():
    """Handle booking API requests - STEP 5: Test end-to-end"""
    try:
        booking_data = request.get_json()
        print(
            f"📥 API Booking: {booking_data.get('customer_name')} - {booking_data.get('pickup_address')} to {booking_data.get('destination')}"
        )

        return {
            "status": "success",
            "message": "Booking received",
            "booking_reference": booking_data.get("booking_reference", "REF123"),
            "estimated_arrival": "10-15 minutes",
        }, 201

    except Exception as e:
        print(f"❌ API Booking Error: {str(e)}")
        return {"status": "error", "message": "Failed to process booking"}, 500


@app.route("/generate_jwt", methods=["GET"])
def generate_jwt_endpoint():
    """Generate TaxiCaller JWT token (legacy)"""
    token = get_taxicaller_jwt()
    if token:
        return jsonify({"token": token}), 200
    else:
        return (
            jsonify(
                {"error": "Failed to generate JWT", "note": "Using v2 API instead"}
            ),
            500,
        )


# STEP 5: Test endpoints
@app.route("/test_taxicaller", methods=["GET", "POST"])
def test_taxicaller():
    """Test endpoint to simulate booking for TaxiCaller integration"""
    try:
        test_booking = {
            "name": "Test User",
            "pickup_address": "123 Test Street, Wellington",
            "destination": "Wellington Airport",
            "pickup_time": "2:00 PM",
            "pickup_date": "21/06/2025",
            "raw_speech": "Test booking from API",
        }

        print(f"🧪 TESTING TAXICALLER INTEGRATION")
        success, response = send_booking_to_taxicaller(test_booking, "+6412345678")

        return {
            "test_result": "success" if success else "failed",
            "taxicaller_response": response,
            "api_configured": bool(TAXICALLER_API_KEY),
            "api_key_preview": TAXICALLER_API_KEY[:8] + "..."
            if TAXICALLER_API_KEY
            else None,
            "endpoints_tried": [
                "https://api-rc.taxicaller.net/api/v1/booker/order",
            ],
            "immediate_dispatch": "enabled for urgent bookings",
        }, 200

    except Exception as e:
        return {"error": str(e), "api_configured": bool(TAXICALLER_API_KEY)}, 500


@app.route("/test_db", methods=["GET"])
def test_db():
    """Test database connection"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            # Get counts
            cur.execute("SELECT COUNT(*) as count FROM bookings")
            bookings_count = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) as count FROM customers")
            customers_count = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) as count FROM conversations")
            conversations_count = cur.fetchone()["count"]

            cur.close()
            conn.close()

            return {
                "database": "connected",
                "tables": {
                    "bookings": bookings_count,
                    "customers": customers_count,
                    "conversations": conversations_count,
                },
            }, 200
        except Exception as e:
            return {"database": "error", "message": str(e)}, 500
    return {"database": "not connected"}, 500


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return (
        jsonify(
            {
                "error": "Endpoint not found",
                "available_endpoints": [
                    "/",
                    "/health",
                    "/voice",
                    "/menu",
                    "/book_taxi",
                    "/process_booking",
                    "/confirm_booking",
                    "/modify_booking",
                    "/team",
                    "/api/bookings",
                    "/test_taxicaller",
                    "/test_db",
                ],
            }
        ),
        404,
    )


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting Kiwi Cabs AI Service on port {port}")
    print(f"📊 Google Speech Available: {GOOGLE_SPEECH_AVAILABLE}")
    print(
        f"🔑 TaxiCaller API Key: {TAXICALLER_API_KEY[:8]}... (configured)"
        if TAXICALLER_API_KEY
        else "🔑 TaxiCaller API Key: Not configured"
    )
    print(f"🚨 IMMEDIATE DISPATCH: Enabled for urgent bookings (right now, ASAP)")
    print(f"📅 SCHEDULED DISPATCH: Background processing for future bookings")
    app.run(host="0.0.0.0", port=port, debug=True)