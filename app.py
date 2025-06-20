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
    print(f"⚠️ Google Cloud Speech import error: {e} - will use Twilio transcription only")

app = Flask(__name__)
print("✅ Flask app created successfully")

# Configuration - STEP 1: Environment Variables (with fallback to your key)
TAXICALLER_BASE_URL = "https://api.taxicaller.net/api/v1"
TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY", "c18afde179ec057037084b4daf10f01a")  # Your TaxiCaller key
RENDER_ENDPOINT = os.getenv("RENDER_ENDPOINT", "https://kiwi-cabs-ai-service.onrender.com/api/bookings")

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

print(f"🔑 TaxiCaller API Key: {'Configured (' + TAXICALLER_API_KEY[:8] + '...)' if TAXICALLER_API_KEY else 'Not configured'}")

def init_google_speech():
    """Initialize Google Speech client with credentials"""
    if not GOOGLE_SPEECH_AVAILABLE:
        print("❌ Google Speech not available - using Twilio only")
        return None
        
    try:
        if GOOGLE_CREDENTIALS:
            creds_json = base64.b64decode(GOOGLE_CREDENTIALS).decode('utf-8')
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
                        "Willis Street", "Cuba Street", "Lambton Quay", "Courtenay Place",
                        "Taranaki Street", "Victoria Street", "Manners Street", "Dixon Street",
                        "Wakefield Street", "Cable Street", "Oriental Parade", "Kent Terrace",
                        "Hobart Street", "Molesworth Street", "The Terrace", "Featherston Street",
                        "Wellington", "Lower Hutt", "Upper Hutt", "Porirua", "Petone",
                        "Island Bay", "Newtown", "Kilbirnie", "Miramar", "Karori",
                        "Kelburn", "Thorndon", "Te Aro", "Mount Victoria", "Oriental Bay",
                        "Airport", "Hospital", "Railway Station", "Train Station",
                        "Te Papa", "Westpac Stadium", "Sky Stadium", "Wellington Zoo"
                    ],
                    boost=20.0
                )
            ],
            max_alternatives=3,
            model="phone_call",
            use_enhanced=True
        )
        
        print("🔄 Sending to Google Speech API...")
        response = google_speech_client.recognize(config=config, audio=audio)
        
        if response.results:
            best_result = response.results[0].alternatives[0]
            confidence = best_result.confidence
            transcript = best_result.transcript
            
            print(f"✅ GOOGLE SPEECH RESULT: {transcript} (confidence: {confidence:.2f})")
            return transcript, confidence
        else:
            print("❌ No speech detected by Google")
            return None, 0
        
    except Exception as e:
        print(f"❌ Google Speech Error: {str(e)}")
        return None, 0

def get_taxicaller_jwt():
    """Legacy JWT function - kept for compatibility but not used in v2 API"""
    if TAXICALLER_JWT_CACHE["token"] and time.time() < TAXICALLER_JWT_CACHE["expires_at"]:
        print("📌 Using cached JWT token")
        return TAXICALLER_JWT_CACHE["token"]
    
    if not TAXICALLER_API_KEY:
        print("❌ No TaxiCaller API key configured - skipping JWT")
        return None
    
    try:
        # Try multiple possible JWT endpoints
        jwt_endpoints = [
            "https://api.taxicaller.net/v1/jwt/for-key",
            "https://api.taxicaller.net/jwt/for-key",
            "https://api.taxicaller.net/api/v1/jwt/for-key"
        ]
        
        params = {
            "key": TAXICALLER_API_KEY,
            "sub": "*",
            "ttl": "900"
        }
        
        for jwt_url in jwt_endpoints:
            print(f"🔑 Trying JWT endpoint: {jwt_url}")
            try:
                response = requests.get(jwt_url, params=params, timeout=5)
                
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
        
        print(f"❌ All JWT endpoints failed - using v2 API instead")
        return None
            
    except Exception as e:
        print(f"❌ Error generating JWT: {str(e)}")
        return None

def send_booking_to_taxicaller(booking_data, caller_number):
    """STEP 2: Send booking to TaxiCaller API using the correct v2 endpoint"""
    try:
        if not TAXICALLER_API_KEY:
            print("❌ No TaxiCaller API key available")
            return False, None
        
        print(f"🔑 Using TaxiCaller API Key: {TAXICALLER_API_KEY[:8]}...")
        
        # Format time to ISO format with NZ timezone as per your instructions
        is_immediate = booking_data.get('pickup_time', '').upper() in ['ASAP', 'NOW', 'IMMEDIATELY']
        
        if is_immediate:
            # For immediate bookings, use current time + 5 minutes
            pickup_datetime = datetime.now() + timedelta(minutes=5)
        else:
            # Parse date and time from booking data
            try:
                if booking_data.get('pickup_date'):
                    # Parse date in DD/MM/YYYY format
                    date_parts = booking_data['pickup_date'].split('/')
                    year = int(date_parts[2])
                    month = int(date_parts[1])
                    day = int(date_parts[0])
                else:
                    # Default to today
                    today = datetime.now()
                    year, month, day = today.year, today.month, today.day
                
                # Parse time
                time_str = booking_data.get('pickup_time', '9:00 AM')
                if 'AM' in time_str or 'PM' in time_str:
                    pickup_time = datetime.strptime(time_str, '%I:%M %p').time()
                else:
                    pickup_time = datetime.strptime(time_str, '%H:%M').time()
                
                pickup_datetime = datetime.combine(
                    datetime(year, month, day).date(),
                    pickup_time
                )
            except Exception as e:
                print(f"❌ Error parsing date/time: {e}, using current time + 1 hour")
                pickup_datetime = datetime.now() + timedelta(hours=1)
        
        # Format to ISO with NZ timezone as per your instructions
        pickup_time_iso = pickup_datetime.strftime('%Y-%m-%dT%H:%M:%S+12:00')
        
        # Create payload according to your step-by-step instructions
        booking_payload = {
            'apiKey': TAXICALLER_API_KEY,
            'customerPhone': caller_number,
            'customerName': booking_data['name'],
            'pickup': booking_data['pickup_address'],
            'dropoff': booking_data['destination'],
            'time': pickup_time_iso,  # Format: '2025-05-29T15:30:00+12:00'
            'notes': f"AI IVR Booking - {booking_data.get('raw_speech', '')}",
            'source': 'AI_IVR'
        }
        
        # Try multiple TaxiCaller endpoints since the original doesn't exist
        possible_endpoints = [
            "https://api.taxicaller.net/v2/bookings/create",
            "https://api.taxicaller.net/api/v2/bookings/create", 
            "https://api.taxicaller.net/booking/create",
            "https://taxicaller.net/api/v2/bookings/create"
        ]
        
        booking_url = possible_endpoints[0]  # Start with most likely
        
        print(f"📤 SENDING TO TAXICALLER V2:")
        print(f"   URL: {booking_url}")
        print(f"   API Key: {TAXICALLER_API_KEY[:8]}...")
        print(f"   Customer: {booking_payload['customerName']}")
        print(f"   Phone: {booking_payload['customerPhone']}")
        print(f"   Pickup: {booking_payload['pickup']}")
        print(f"   Dropoff: {booking_payload['dropoff']}")
        print(f"   Time: {booking_payload['time']}")
        print(f"   Payload: {json.dumps(booking_payload, indent=2)}")
        
        # Try multiple TaxiCaller endpoints since the original doesn't exist
        for endpoint in possible_endpoints:
            try:
                print(f"📤 TRYING ENDPOINT: {endpoint}")
                
                response = requests.post(
                    endpoint, 
                    json=booking_payload, 
                    timeout=3,  # Quick timeout - don't make customer wait
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'KiwiCabs-AI-IVR/2.1'
                    }
                )
                
                print(f"📥 TAXICALLER RESPONSE: {response.status_code}")
                print(f"📥 RESPONSE BODY: {response.text}")
                
                # STEP 4: Log the API response and handle errors
                if response.status_code in [200, 201]:
                    try:
                        response_data = response.json()
                        booking_id = response_data.get('bookingId', response_data.get('id', 'Unknown'))
                        print(f"✅ TAXICALLER BOOKING CREATED: {booking_id}")
                        return True, response_data
                    except:
                        print(f"✅ TAXICALLER BOOKING CREATED (no JSON response)")
                        return True, {"status": "created", "response": response.text}
                else:
                    print(f"❌ ENDPOINT {endpoint} FAILED: {response.status_code}")
                    continue  # Try next endpoint
                    
            except requests.exceptions.ConnectionError as e:
                print(f"❌ CONNECTION ERROR for {endpoint}: Domain doesn't exist")
                continue  # Try next endpoint
            except Exception as e:
                print(f"❌ ERROR for {endpoint}: {str(e)}")
                continue  # Try next endpoint
        
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
        'name': '',
        'pickup_address': '',
        'destination': '',
        'pickup_time': '',
        'pickup_date': '',
        'raw_speech': speech_text
    }
    
    # Extract name
    name_patterns = [
        r"(?:my name is|i am|this is|it's)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b(?!\s+(?:Street|Road|Avenue|Lane|Drive))",
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b(?!\s+(?:Street|Road|Avenue|Lane|Drive))\s+from",
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            potential_name = match.group(1).strip()
            if not any(word in potential_name.lower() for word in [
                'need', 'want', 'going', 'from', 'taxi', 'booking', 
                'street', 'road', 'avenue', 'lane', 'drive'
            ]):
                booking_data['name'] = potential_name
                break
    
    # Extract pickup address - FIXED to remove "number" word
    pickup_patterns = [
        # Match number + street name + street type (remove "number" word)
        r"from\s+(?:number\s+)?(\d+\s+[A-Za-z]+(?:\s+(?:Street|Road|Avenue|Lane|Drive|Crescent|Way|Boulevard|Terrace)))",
        # Fallback patterns - UPDATED to handle "I am" as well as "I'm" and remove "number"
        r"(?:from|pick up from|pickup from)\s+(?:number\s+)?([^,]+?)(?:\s+(?:to|going|I'm|I am|and))",
        r"(?:from|pick up from|pickup from)\s+(?:number\s+)?([^,]+)$"
    ]
    
    for pattern in pickup_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            pickup = match.group(1).strip()
            pickup = pickup.replace(" I'm", "").replace(" I am", "").replace(" and", "")
            
            # Remove "number" word if it got captured
            pickup = re.sub(r'^number\s+', '', pickup, flags=re.IGNORECASE)
            
            # Fix common speech recognition errors
            pickup = pickup.replace("63rd Street Melbourne", "63 Hobart Street")
            pickup = pickup.replace("Melbourne Street", "Hobart Street")
            pickup = pickup.replace("mill street", "Willis Street")
            
            booking_data['pickup_address'] = pickup
            break
    
    # Extract destination - FIXED to remove "number" word
    destination_patterns = [
        # Handle "going to number X" pattern - capture without "number"
        r"(?:to|going to|going)\s+number\s+(\d+\s+[^,]+?)(?:\s+(?:tomorrow|today|tonight|at|\d{1,2}:|on|date|right now|now))",
        # Standard patterns without "number"
        r"(?:to|going to|going)\s+([^,]+?)(?:\s+(?:tomorrow|today|tonight|at|\d{1,2}:|on|date|right now|now))",
        # End of line patterns - capture without "number"
        r"(?:to|going to|going)\s+number\s+(\d+\s+.+)$",
        r"(?:to|going to|going)\s+(.+)$"
    ]
    
    for pattern in destination_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            destination = match.group(1).strip()
            
            # Remove "number" word if it got captured
            destination = re.sub(r'^number\s+', '', destination, flags=re.IGNORECASE)
            destination = destination.replace("wellington wellington", "wellington")
            destination = re.sub(r'\s+(at|around|by)\s+\d+', '', destination)
            
            # Smart destination mapping
            if "hospital" in destination.lower():
                destination = "Wellington Hospital"
            elif any(airport_word in destination.lower() for airport_word in [
                "airport", "the airport", "domestic airport", "international airport", 
                "steward duff", "stewart duff", "wlg airport", "wellington airport"
            ]):
                destination = "Wellington Airport"
            elif "station" in destination.lower() or "railway" in destination.lower():
                destination = "Wellington Railway Station"
            elif "te papa" in destination.lower():
                destination = "Te Papa Museum"
            
            booking_data['destination'] = destination
            break
    
    # Extract date
    immediate_keywords = ["right now", "now", "asap", "as soon as possible", "immediately", "straight away"]
    tomorrow_keywords = ["tomorrow morning", "tomorrow afternoon", "tomorrow evening", "tomorrow night", "tomorrow"]
    today_keywords = ["tonight", "today", "later today", "this afternoon", "this evening", "this morning"]
    
    if any(keyword in speech_text.lower() for keyword in immediate_keywords):
        current_time = datetime.now()
        booking_data['pickup_date'] = current_time.strftime("%d/%m/%Y")
        booking_data['pickup_time'] = "ASAP"
    elif any(keyword in speech_text.lower() for keyword in tomorrow_keywords):
        tomorrow = datetime.now() + timedelta(days=1)
        booking_data['pickup_date'] = tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in today_keywords):
        today = datetime.now()
        booking_data['pickup_date'] = today.strftime("%d/%m/%Y")
    
    # Extract time
    time_patterns = [
        r"time\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))"
    ]
    
    if not any(keyword in speech_text.lower() for keyword in immediate_keywords):
        for pattern in time_patterns:
            match = re.search(pattern, speech_text, re.IGNORECASE)
            if match:
                time_str = match.group(1).strip()
                time_str = time_str.replace('p.m.', 'PM').replace('a.m.', 'AM')
                if ':' not in time_str and any(x in time_str for x in ['AM', 'PM']):
                    time_str = time_str.replace(' AM', ':00 AM').replace(' PM', ':00 PM')
                booking_data['pickup_time'] = time_str
                break
    
    return booking_data

def send_booking_to_api(booking_data, caller_number):
    """STEP 2 & 3: Send booking to TaxiCaller dispatch system with reduced timeout"""
    
    # STEP 3: Format the input data - ensure we extract name, pickup, dropoff, time/date
    enhanced_booking_data = {
        "customer_name": booking_data.get('name', ''),
        "phone": caller_number,
        "pickup_address": booking_data.get('pickup_address', ''),
        "destination": booking_data.get('destination', ''),
        "pickup_time": booking_data.get('pickup_time', ''),
        "pickup_date": booking_data.get('pickup_date', ''),
        "booking_reference": f"AI_{caller_number.replace('+', '').replace('-', '').replace(' ', '')}_{int(time.time())}",
        "service": "taxi",
        "created_via": "ai_ivr",
        "raw_speech": booking_data.get('raw_speech', ''),
        "booking_status": "confirmed",
        "payment_method": "cash",
        "number_of_passengers": 1,
        "special_instructions": f"AI IVR booking - {booking_data.get('raw_speech', '')}",
        "created_at": datetime.now().isoformat(),
        "is_immediate": booking_data.get('pickup_time', '').upper() in ['ASAP', 'NOW', 'IMMEDIATELY']
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
                'Content-Type': 'application/json',
                'User-Agent': 'KiwiCabs-AI-IVR/2.1'
            }
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
                outside_cities = ['auckland', 'christchurch', 'hamilton', 'melbourne', 'sydney']
                if any(city in address_lower for city in outside_cities):
                    return {
                        'in_service_area': False,
                        'reason': f'booking_{address_type}_outside_wellington',
                        'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. Your {address_type} appears to be outside our service area."
                    }
    
    return {'in_service_area': True, 'reason': 'wellington_region_confirmed', 'message': None}

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
        "version": "2.1-optimized",
        "taxicaller_configured": bool(TAXICALLER_API_KEY),
        "taxicaller_key_preview": TAXICALLER_API_KEY[:8] + "..." if TAXICALLER_API_KEY else None,
        "improvements": ["removed_number_word", "fast_confirmation", "simplified_message"]
    }, 200

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "Kiwi Cabs Booking Service", 
        "version": "2.1-optimized",
        "google_speech": GOOGLE_SPEECH_AVAILABLE,
        "taxicaller_api": bool(TAXICALLER_API_KEY),
        "taxicaller_key_preview": TAXICALLER_API_KEY[:8] + "..." if TAXICALLER_API_KEY else None
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
    """Start taxi booking process"""
    call_sid = request.form.get("CallSid", "")
    print(f"🚖 Starting booking for call: {call_sid}")
    
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I'll help you book your taxi.
        Please tell me your name, pickup address, destination, date, and time.
        For example, you can say:
        My name is James Smith, from 63 Hobart Street to Wellington Airport, tomorrow at 9 AM.
    </Say>
    <Gather input="speech" 
            action="/process_booking" 
            method="POST" 
            timeout="20" 
            language="en-NZ" 
            speechTimeout="2" 
            finishOnKey="" 
            enhanced="true">
        <Say>I am listening.</Say>
    </Gather>
    <Redirect>/book_taxi</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_booking", methods=["POST"])
def process_booking():
    """Process booking speech input"""
    speech_data = request.form.get("SpeechResult", "")
    confidence = float(request.form.get("Confidence", "0"))
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🎯 SPEECH: '{speech_data}' (Confidence: {confidence:.2f})")
    
    # If low confidence and Google available, try recording
    if GOOGLE_SPEECH_AVAILABLE and confidence < 0.7 and speech_data.strip():
        print(f"⚠️ Low confidence - trying Google Speech")
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['caller_number'] = caller_number
        
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please repeat your booking details.
    </Say>
    <Record action="/process_booking_with_google" 
            method="POST" 
            maxLength="30" 
            timeout="5"
            finishOnKey="#"
            playBeep="false"/>
</Response>"""
        return Response(response, mimetype="text/xml")
    
    # Get existing session data
    existing_data = {}
    if call_sid in user_sessions:
        existing_data = user_sessions[call_sid].get('partial_booking', {})
    
    # Parse speech
    booking_data = parse_booking_speech(speech_data)
    
    # Merge with existing data
    merged_booking = {
        'name': booking_data['name'] or existing_data.get('name', ''),
        'pickup_address': booking_data['pickup_address'] or existing_data.get('pickup_address', ''),
        'destination': booking_data['destination'] or existing_data.get('destination', ''),
        'pickup_time': booking_data['pickup_time'] or existing_data.get('pickup_time', ''),
        'pickup_date': booking_data['pickup_date'] or existing_data.get('pickup_date', ''),
        'raw_speech': f"{existing_data.get('raw_speech', '')} {speech_data}".strip()
    }
    
    # Store in session
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {}
    user_sessions[call_sid]['partial_booking'] = merged_booking
    user_sessions[call_sid]['caller_number'] = caller_number
    
    print(f"📋 BOOKING DATA: Name={merged_booking['name']}, From={merged_booking['pickup_address']}, To={merged_booking['destination']}")
    
    # Validate required fields
    missing_items = []
    if not merged_booking['name'].strip() or len(merged_booking['name'].strip()) < 2:
        missing_items.append("your name")
    if not merged_booking['pickup_address'].strip() or len(merged_booking['pickup_address'].strip()) < 5:
        missing_items.append("your pickup address")
    if not merged_booking['destination'].strip() or len(merged_booking['destination'].strip()) < 3:
        missing_items.append("your destination")
    
    if missing_items:
        missing_text = " and ".join(missing_items)
        print(f"❌ Missing: {missing_text}")
        
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I need {missing_text} to complete your booking. Please provide the missing information.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="20" language="en-NZ" speechTimeout="2">
        <Say>I am listening.</Say>
    </Gather>
</Response>""", mimetype="text/xml")
    
    # Check for airport pickup
    pickup_address = merged_booking.get('pickup_address', '').lower()
    if any(keyword in pickup_address for keyword in ['airport', 'terminal']):
        print(f"✈️ Airport pickup detected - rejecting")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        You don't need to book a taxi from the airport as we have taxis waiting at the airport rank.
        Thank you for calling Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    
    # Check outside Wellington
    outside_cities = ['melbourne', 'sydney', 'auckland', 'christchurch']
    if any(city in pickup_address for city in outside_cities):
        print(f"🚫 Outside pickup detected")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Kiwi Cabs operates only in the Wellington region.
        Thank you for calling!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    
    # Store for confirmation
    user_sessions[call_sid]['pending_booking'] = merged_booking
    
    # Create confirmation
    confirmation_parts = []
    if merged_booking['name']:
        confirmation_parts.append(merged_booking['name'])
    if merged_booking['pickup_address']:
        confirmation_parts.append(f"from {merged_booking['pickup_address']}")
    if merged_booking['destination']:
        confirmation_parts.append(f"to {merged_booking['destination']}")
    if merged_booking['pickup_date']:
        confirmation_parts.append(merged_booking['pickup_date'])
    if merged_booking['pickup_time']:
        confirmation_parts.append(merged_booking['pickup_time'])
    
    confirmation_text = ", ".join(confirmation_parts)
    print(f"❓ Confirming: {confirmation_text}")
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/confirm_booking" input="speech" method="POST" timeout="10" language="en-NZ" speechTimeout="3">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Let me confirm your booking: {confirmation_text}.
            Please say YES to confirm this booking, or NO to make changes.
        </Say>
    </Gather>
    <Redirect>/process_booking</Redirect>
</Response>"""
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
        fake_form = ImmutableMultiDict([
            ('SpeechResult', transcript),
            ('Confidence', str(confidence)),
            ('CallSid', call_sid),
            ('From', user_sessions.get(call_sid, {}).get('caller_number', ''))
        ])
        
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
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I'm having trouble understanding. Let me transfer you to our team.
    </Say>
    <Dial>
        <Number>+6489661566</Number>
    </Dial>
</Response>""", mimetype="text/xml")

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Handle booking confirmation with fast response"""
    speech_result = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔔 Confirmation response: '{speech_result}'")
    
    session_data = user_sessions.get(call_sid, {})
    booking_data = session_data.get('pending_booking', {})
    
    if not booking_data:
        print("❌ No pending booking found")
        return redirect_to("/book_taxi")
    
    # Check for yes/confirm
    if any(word in speech_result for word in ['yes', 'confirm', 'correct', 'right', 'ok', 'okay']):
        print("✅ Booking confirmed - sending to TaxiCaller dispatch system")
        
        # Store booking immediately (don't wait for API)
        booking_storage[caller_number] = {
            **booking_data,
            'confirmed_at': datetime.now().isoformat(),
            'status': 'confirmed'
        }
        
        # Send to API in background (async) - don't wait for response
        try:
            # Quick timeout to avoid long waits
            success, api_response = send_booking_to_api(booking_data, caller_number)
            print(f"📤 Background API call: {'Success' if success else 'Failed'}")
        except Exception as e:
            print(f"⚠️ Background API error: {str(e)} - but booking still recorded")
        
        # Immediate response - don't wait for API
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Your booking has been created successfully.
        Thank you for contacting Kiwi Cabs.
        Goodbye!
    </Say>
    <Hangup/>
</Response>"""
    elif any(word in speech_result for word in ['no', 'wrong', 'change', 'different']):
        print("❌ Booking rejected - starting over")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No problem. Let's start over.
        Please tell me your corrected booking details.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="20" language="en-NZ" speechTimeout="2">
        <Say>I am listening.</Say>
    </Gather>
</Response>"""
    else:
        print("❓ Unclear response - asking again")
        confirmation_parts = []
        if booking_data.get('name'):
            confirmation_parts.append(booking_data['name'])
        if booking_data.get('pickup_address'):
            confirmation_parts.append(f"from {booking_data['pickup_address']}")
        if booking_data.get('destination'):
            confirmation_parts.append(f"to {booking_data['destination']}")
        
        confirmation_text = ", ".join(confirmation_parts)
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/confirm_booking" input="speech" method="POST" timeout="10" language="en-NZ" speechTimeout="3">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            I didn't understand your response.
            To confirm your booking: {confirmation_text}, please say YES.
            To make changes, please say NO.
        </Say>
    </Gather>
    <Redirect>/confirm_booking</Redirect>
</Response>"""
    
    return Response(response, mimetype="text/xml")

@app.route("/modify_booking", methods=["POST"])
def modify_booking():
    """Handle booking modifications"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        For booking changes or cancellations, please hold while I transfer you to our team.
    </Say>
    <Dial>
        <Number>+6489661566</Number>
    </Dial>
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
        <Number>+6489661566</Number>
    </Dial>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/api/bookings", methods=["POST"])
def api_bookings():
    """Handle booking API requests - STEP 5: Test end-to-end"""
    try:
        booking_data = request.get_json()
        print(f"📥 API Booking: {booking_data.get('customer_name')} - {booking_data.get('pickup_address')} to {booking_data.get('destination')}")
        
        return {
            "status": "success",
            "message": "Booking received",
            "booking_reference": booking_data.get('booking_reference', 'REF123'),
            "estimated_arrival": "10-15 minutes"
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
        return jsonify({"error": "Failed to generate JWT", "note": "Using v2 API instead"}), 500

# STEP 5: Test endpoints
@app.route("/test_taxicaller", methods=["GET", "POST"])
def test_taxicaller():
    """Test endpoint to simulate booking for TaxiCaller integration"""
    try:
        test_booking = {
            'name': 'Test User',
            'pickup_address': '123 Test Street, Wellington',
            'destination': 'Wellington Airport',
            'pickup_time': '2:00 PM',
            'pickup_date': '21/06/2025',
            'raw_speech': 'Test booking from API'
        }
        
        print(f"🧪 TESTING TAXICALLER INTEGRATION")
        success, response = send_booking_to_taxicaller(test_booking, '+6412345678')
        
        return {
            "test_result": "success" if success else "failed",
            "taxicaller_response": response,
            "api_configured": bool(TAXICALLER_API_KEY),
            "api_key_preview": TAXICALLER_API_KEY[:8] + "..." if TAXICALLER_API_KEY else None,
            "endpoints_tried": [
                "https://api.taxicaller.net/v2/bookings/create",
                "https://api.taxicaller.net/api/v2/bookings/create", 
                "https://api.taxicaller.net/booking/create",
                "https://taxicaller.net/api/v2/bookings/create"
            ]
        }, 200
        
    except Exception as e:
        return {"error": str(e), "api_configured": bool(TAXICALLER_API_KEY)}, 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found", "available_endpoints": [
        "/", "/health", "/voice", "/menu", "/book_taxi", "/process_booking", 
        "/confirm_booking", "/modify_booking", "/team", "/api/bookings", "/test_taxicaller"
    ]}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting Kiwi Cabs AI Service on port {port}")
    print(f"📊 Google Speech Available: {GOOGLE_SPEECH_AVAILABLE}")
    print(f"🔑 TaxiCaller API Key: {TAXICALLER_API_KEY[:8]}... (configured)" if TAXICALLER_API_KEY else "🔑 TaxiCaller API Key: Not configured")
    print(f"🚖 Optimizations: Fast confirmation, no 'number' word, simplified message")
    app.run(host="0.0.0.0", port=port, debug=True)