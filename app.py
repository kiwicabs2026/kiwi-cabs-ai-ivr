import os
import requests
import json
from flask import Flask, request, Response, jsonify
from datetime import datetime, timedelta
import re
import urllib.parse
import time
import base64

# Try to import Google Cloud Speech, but make it optional
try:
    from google.cloud import speech
    from google.oauth2 import service_account
    GOOGLE_SPEECH_AVAILABLE = True
except ImportError:
    print("⚠️ Google Cloud Speech not available - will use Twilio transcription only")
    GOOGLE_SPEECH_AVAILABLE = False

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OpenAI API key is not set in environment variable OPENAI_API_KEY")

def extract_booking_details(text):
    prompt = f"""
Extract the following details from the text:

- Name  
- Pickup location  
- Drop-off location  
- Date and time  

Return the result as a JSON object with keys: name, pickup, dropoff, datetime.

Text: "{text}"
"""

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts structured data."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=150
    )

    extracted_text = response.choices[0].message.content.strip()
    # Remove markdown code blocks if present
    cleaned = re.sub(r"```json|```", "", extracted_text).strip()

    try:
        data = json.loads(cleaned)
        return data
    except Exception as e:
        print("Error parsing JSON:", e)
        print("Raw response:", extracted_text)
        return None


@app.route('/ask', methods=['POST'])
def ask():
    transcription = request.form.get('SpeechResult', '')
    details = extract_booking_details(transcription)

    response = VoiceResponse()

    if not details:
        response.say("Sorry, we could not understand your request. Please try again.")
        response.hangup()
        return Response(str(response), mimetype='application/xml')

    name = details.get('name', 'Guest')
    pickup = details.get('pickup', 'Unknown')
    dropoff = details.get('dropoff', 'Unknown')
    datetime_text = details.get('datetime', 'Unknown')

    # Redirect to confirmation with extracted details as query params
    response.redirect(f"/confirm_booking?name={name}&pickup={pickup}&dropoff={dropoff}&datetime={datetime_text}")
    return Response(str(response), mimetype='application/xml')

@app.route('/confirm_booking', methods=['GET', 'POST'])
def confirm_booking():
    name = request.args.get('name', 'Guest')
    pickup = request.args.get('pickup', 'Unknown')
    dropoff = request.args.get('dropoff', 'Unknown')
    datetime_text = request.args.get('datetime', 'Unknown')

    response = VoiceResponse()
    gather = Gather(num_digits=1, action='/handle_confirmation', method='POST')
    gather.say(f"Thanks {name}. You’ve requested a taxi from {pickup} to {dropoff} at {datetime_text}. "
               "If that’s correct, press 1. To cancel, press 2.")
    response.append(gather)

    response.say("We didn't get your response. Goodbye.")
    response.hangup()
    return Response(str(response), mimetype='application/xml')

@app.route('/handle_confirmation', methods=['POST'])
def handle_confirmation():
    digit = request.form.get('Digits')
    response = VoiceResponse()

    if digit == '1':
        response.say("Your taxi booking is confirmed. Thank you! Goodbye.")
        # TODO: Add database save or SMS confirmation here
    elif digit == '2':
        response.say("Your booking has been canceled. Goodbye.")
    else:
        response.say("Invalid input. Goodbye.")

    response.hangup()
    return Response(str(response), mimetype='application/xml')

# TaxiCaller API Configuration
TAXICALLER_BASE_URL = "https://api.taxicaller.net/api/v1"
TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY", "")
RENDER_ENDPOINT = os.getenv("RENDER_ENDPOINT", "https://kiwi-cabs-ai-service.onrender.com/api/bookings")

# Google Cloud and Twilio Configuration
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CLOUD_CREDENTIALS", "")  # Base64 encoded JSON
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")

# JWT Token Cache
TAXICALLER_JWT_CACHE = {"token": None, "expires_at": 0}

# Session memory stores
user_sessions = {}
modification_bookings = {}
# Simple booking storage - stores all bookings by phone number
booking_storage = {}

# Initialize Google Speech client
def init_google_speech():
    """Initialize Google Speech client with credentials"""
    if not GOOGLE_SPEECH_AVAILABLE:
        return None
        
    try:
        if GOOGLE_CREDENTIALS:
            # Decode base64 credentials
            creds_json = base64.b64decode(GOOGLE_CREDENTIALS).decode('utf-8')
            credentials = service_account.Credentials.from_service_account_info(
                json.loads(creds_json)
            )
            print("✅ Google Speech client initialized successfully")
            return speech.SpeechClient(credentials=credentials)
        print("❌ No Google credentials found")
        return None
    except Exception as e:
        print(f"❌ Failed to initialize Google Speech: {str(e)}")
        return None

# Initialize client once at startup
google_speech_client = init_google_speech()

def transcribe_with_google(audio_url):
    """Use Google Speech for better transcription"""
    if not GOOGLE_SPEECH_AVAILABLE or not google_speech_client:
        print("❌ Google Speech client not available")
        return None, 0
        
    try:
        print(f"🎤 Fetching audio from: {audio_url}")
        
        # Download audio from Twilio
        response = requests.get(audio_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        if response.status_code != 200:
            print(f"❌ Failed to download audio: {response.status_code}")
            return None, 0
            
        audio_content = response.content
        print(f"✅ Downloaded audio: {len(audio_content)} bytes")
        
        # Configure Google Speech for NZ English
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,  # Phone audio rate
            language_code="en-NZ",   # New Zealand English
            enable_automatic_punctuation=True,
            enable_word_confidence=True,
            # Add speech context for better recognition of NZ places
            speech_contexts=[
                speech.SpeechContext(
                    phrases=[
                        # Common NZ streets
                        "Willis Street", "Cuba Street", "Lambton Quay", "Courtenay Place",
                        "Taranaki Street", "Victoria Street", "Manners Street", "Dixon Street",
                        "Wakefield Street", "Cable Street", "Oriental Parade", "Kent Terrace",
                        "Hobart Street", "Molesworth Street", "The Terrace", "Featherston Street",
                        # Wellington suburbs
                        "Wellington", "Lower Hutt", "Upper Hutt", "Porirua", "Petone",
                        "Island Bay", "Newtown", "Kilbirnie", "Miramar", "Karori",
                        "Kelburn", "Thorndon", "Te Aro", "Mount Victoria", "Oriental Bay",
                        "Wadestown", "Khandallah", "Ngaio", "Johnsonville", "Tawa",
                        # Common destinations
                        "Airport", "Hospital", "Railway Station", "Train Station",
                        "Te Papa", "Westpac Stadium", "Sky Stadium", "Wellington Zoo",
                        # Numbers as words
                        "one", "two", "three", "four", "five", "six", "seven",
                        "eight", "nine", "ten", "eleven", "twelve", "thirteen",
                        "fourteen", "fifteen", "twenty", "thirty", "forty", "fifty",
                        # Time words
                        "quarter past", "half past", "o'clock", "midnight", "midday",
                        "morning", "afternoon", "evening", "tonight", "tomorrow", "today"
                    ],
                    boost=20.0  # Strongly boost recognition of these phrases
                )
            ],
            # Get alternatives for comparison
            max_alternatives=3,
            # Use enhanced model for better accuracy
            model="phone_call",
            use_enhanced=True
        )
        
        print("🔄 Sending to Google Speech API...")
        
        # Perform the transcription
        response = google_speech_client.recognize(config=config, audio=audio)
        
        # Get the best result
        if response.results:
            best_result = response.results[0].alternatives[0]
            confidence = best_result.confidence
            transcript = best_result.transcript
            
            print(f"✅ GOOGLE SPEECH RESULT:")
            print(f"   Transcript: {transcript}")
            print(f"   Confidence: {confidence:.2f}")
            
            # Show alternatives if available
            if len(response.results[0].alternatives) > 1:
                print(f"   Other possibilities:")
                for i, alt in enumerate(response.results[0].alternatives[1:], 1):
                    print(f"     {i}. {alt.transcript} (confidence: {alt.confidence:.2f})")
            
            return transcript, confidence
        else:
            print("❌ No speech detected by Google")
            return None, 0
        
    except Exception as e:
        print(f"❌ Google Speech Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, 0

def get_taxicaller_jwt():
    """Get or refresh JWT token for TaxiCaller API"""
    # Check if we have a valid cached token
    if TAXICALLER_JWT_CACHE["token"] and time.time() < TAXICALLER_JWT_CACHE["expires_at"]:
        print("📌 Using cached JWT token")
        return TAXICALLER_JWT_CACHE["token"]
    
    if not TAXICALLER_API_KEY:
        print("❌ No TaxiCaller API key configured")
        return None
    except Exception as e:
        print(f"❌ Google Speech Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, 0
    try:
        # Generate new JWT token
        jwt_url = f"https://api.taxicaller.net/v1/jwt/for-key"
        params = {
            "key": TAXICALLER_API_KEY,
            "sub": "*",  # All subjects
            "ttl": "900"  # 15 minutes (max allowed)
        }
        
        print(f"🔑 Generating new JWT token...")
        response = requests.get(jwt_url, params=params, timeout=10)
        
        if response.status_code == 200:
            jwt_token = response.text.strip()  # JWT is returned as plain text
            
            # Cache the token (expires in 14 minutes to be safe)
            TAXICALLER_JWT_CACHE["token"] = jwt_token
            TAXICALLER_JWT_CACHE["expires_at"] = time.time() + 840  # 14 minutes
            
            print(f"✅ JWT token generated successfully")
            return jwt_token
        else:
            print(f"❌ Failed to generate JWT: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error generating JWT: {str(e)}")
        return None

def cancel_booking_in_taxicaller(booking_id, caller_number):
    """Cancel existing booking in TaxiCaller before creating modified one"""
    try:
        # Get JWT token
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            print("❌ No JWT token available for cancellation")
            return False
        
        # TaxiCaller cancel endpoint
        cancel_url = f"https://api.taxicaller.net/Booking/v1/bookings/{booking_id}/cancel"
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        cancel_payload = {
            "reason": "Customer modification request",
            "cancelledBy": "IVR_System"
        }
        
        print(f"🗑️ CANCELLING OLD BOOKING: {booking_id}")
        
        response = requests.post(
            cancel_url,
            json=cancel_payload,
            headers=headers,
            timeout=5
        )
        
        print(f"📥 CANCEL RESPONSE: {response.status_code}")
        print(f"   Body: {response.text}")
        
        if response.status_code in [200, 201, 204]:
            print(f"✅ OLD BOOKING CANCELLED: {booking_id}")
            return True
        else:
            print(f"❌ CANCEL FAILED: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ CANCEL ERROR: {str(e)}")
        return False

def send_booking_to_taxicaller(booking_data, caller_number):
    """Send booking to TaxiCaller API using JWT authentication"""
    try:
        # Get JWT token
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            print("❌ No JWT token available")
            return False, None
        
        # Prepare TaxiCaller booking payload
        # Determine if booking is "Now" or "Later"
        is_immediate = booking_data.get('pickup_time', '').upper() in ['ASAP', 'NOW', 'IMMEDIATELY']
        
        if is_immediate:
            # For immediate bookings - use current date/time
            current_time = datetime.now()
            formatted_date = current_time.strftime("%Y-%m-%d")
            formatted_time = current_time.strftime("%H:%M")
            booking_when = "NOW"
        else:
            # For scheduled bookings - format the provided date/time
            if booking_data['pickup_date']:
                date_parts = booking_data['pickup_date'].split('/')
                formatted_date = f"{date_parts[2]}-{date_parts[1].zfill(2)}-{date_parts[0].zfill(2)}"
            else:
                # Default to today if no date provided
                formatted_date = datetime.now().strftime("%Y-%m-%d")
            
            # Format time for TaxiCaller (24-hour format)
            formatted_time = booking_data.get('pickup_time', '').replace(' AM', '').replace(' PM', '')
            if 'PM' in booking_data.get('pickup_time', '') and not formatted_time.startswith('12'):
                # Convert PM to 24-hour format
                hour_parts = formatted_time.split(':')
                if len(hour_parts) == 2:
                    formatted_time = f"{int(hour_parts[0]) + 12}:{hour_parts[1]}"
            booking_when = "LATER"
        
        taxicaller_payload = {
            "bookingKey": f"IVR_{caller_number}_{int(time.time())}",
            "passengerName": booking_data['name'],
            "passengerPhone": caller_number,
            "pickupAddress": booking_data['pickup_address'],
            "destinationAddress": booking_data['destination'],
            "pickupDate": formatted_date,
            "pickupTime": formatted_time,
            "when": booking_when,  # "NOW" or "LATER"
            "numberOfPassengers": 1,
            "paymentMethod": "CASH",
            "notes": f"AI IVR Booking - {booking_data.get('raw_speech', '')}",
            "bookingSource": "IVR"
        }
        
        # API endpoint for creating bookings
        booking_url = "https://api.taxicaller.net/Booking/v1/bookings"
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        print(f"📤 SENDING TO TAXICALLER:")
        print(f"   URL: {booking_url}")
        print(f"   When: {booking_when}")
        print(f"   Date: {formatted_date}")
        print(f"   Time: {formatted_time}")
        print(f"   Payload: {json.dumps(taxicaller_payload, indent=2)}")
        
        response = requests.post(
            booking_url,
            json=taxicaller_payload,
            headers=headers,
            timeout=2
        )
        
        print(f"📥 TAXICALLER RESPONSE: {response.status_code}")
        print(f"   Body: {response.text}")
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            booking_id = response_data.get('bookingId', 'Unknown')
            
            print(f"✅ BOOKING CREATED IN TAXICALLER")
            print(f"   Booking ID: {booking_id}")
            
            return True, response_data
        else:
            print(f"❌ TAXICALLER API ERROR: {response.status_code}")
            print(f"   Error: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ TAXICALLER API ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None

def parse_booking_speech(speech_text):
    """Parse booking details from speech input including NZ date format"""
    booking_data = {
        'name': '',
        'pickup_address': '',
        'destination': '',
        'pickup_time': '',
        'pickup_date': '',
        'raw_speech': speech_text
    }
    
    # Extract name - IMPROVED patterns that exclude street names
    name_patterns = [
        # Handle possessive forms like "Saddam Hussein's"
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'s\s+from",
        # Standard introduction patterns
        r"(?:my name is|i am|this is|it's)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        # Names at start of sentence, but NOT followed by street types
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b(?!\s+(?:Street|Road|Avenue|Lane|Drive|Crescent|Way|Boulevard|Terrace))",
        # Names before "from" but not street names
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b(?!\s+(?:Street|Road|Avenue|Lane|Drive))\s+from",
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            potential_name = match.group(1).strip()
            # Filter out common non-name words and street names
            if not any(word in potential_name.lower() for word in [
                'need', 'want', 'going', 'from', 'taxi', 'booking', 
                'street', 'road', 'avenue', 'lane', 'drive', 'crescent', 
                'way', 'boulevard', 'terrace', 'hobart', 'willis', 'cuba'
            ]):
                booking_data['name'] = potential_name
                break
    
    # Extract pickup address - IMPROVED with proper address patterns
    pickup_patterns = [
        # Match number + street name + street type
        r"from\s+(\d+\s+[A-Za-z]+(?:\s+(?:Street|Road|Avenue|Lane|Drive|Crescent|Way|Boulevard|Terrace)))",
        # Fallback patterns - UPDATED to handle "I am" as well as "I'm"
        r"(?:from|pick up from|pickup from)\s+([^,]+?)(?:\s+(?:to|going|I'm|I am|and))",
        r"(?:from|pick up from|pickup from)\s+([^,]+)$"
    ]
    
    for pattern in pickup_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            pickup = match.group(1).strip()
            # Simple cleanup
            pickup = pickup.replace(" I'm", "").replace(" I am", "").replace(" and", "")
            
            # Fix common speech recognition errors for Wellington streets
            pickup = pickup.replace("63rd Street Melbourne", "63 Hobart Street")
            pickup = pickup.replace("Melbourne Street", "Hobart Street")
            pickup = pickup.replace("mill street", "Willis Street")
            pickup = pickup.replace("labor key", "Lambton Quay")
            
            booking_data['pickup_address'] = pickup
            break
    
    # Extract destination - FIXED to handle "number" prefix and common patterns
    destination_patterns = [
        # Handle "going to number X" pattern specifically
        r"(?:to|going to|going)\s+number\s+(\d+\s+[^,]+?)(?:\s+(?:tomorrow|today|tonight|at|\d{1,2}:|on|date|right now|now))",
        # Standard patterns without "number"
        r"(?:to|going to|going)\s+([^,]+?)(?:\s+(?:tomorrow|today|tonight|at|\d{1,2}:|on|date|right now|now))",
        # End of line patterns
        r"(?:to|going to|going)\s+number\s+(\d+\s+.+)$",
        r"(?:to|going to|going)\s+(.+)$"
    ]
    
    for pattern in destination_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            destination = match.group(1).strip()
            
            # Clean up common issues
            destination = destination.replace("wellington wellington", "wellington")
            # Remove trailing time indicators that might have been captured
            destination = re.sub(r'\s+(at|around|by)\s+\d+', '', destination)
            # Clean up "te aro" if it got split
            destination = re.sub(r'\s+te\s+aro', ', Te Aro', destination, flags=re.IGNORECASE)
            
            # Smart destination mapping - comprehensive airport detection
            if "hospital" in destination.lower():
                destination = "Wellington Hospital"
            elif any(airport_word in destination.lower() for airport_word in [
                "airport", "the airport", "domestic airport", "international airport", 
                "steward duff", "stewart duff", "steward duff driver airport", 
                "stewart duff driver airport", "wlg airport", "wellington airport"
            ]):
                destination = "Wellington Airport"
            elif "station" in destination.lower() or "railway" in destination.lower():
                destination = "Wellington Railway Station"
            elif "te papa" in destination.lower():
                destination = "Te Papa Museum"
            elif "cbd" in destination.lower() or "city centre" in destination.lower():
                destination = "Wellington CBD"
            
            booking_data['destination'] = destination
            break
    
    # Extract date - intelligent parsing for natural language
    from datetime import datetime, timedelta
    
    # RIGHT NOW / ASAP keywords = current date and immediate time
    immediate_keywords = ["right now", "now", "asap", "as soon as possible", "immediately", "straight away"]
    
    # AFTER TOMORROW keywords = day after tomorrow (+2 days)
    after_tomorrow_keywords = ["after tomorrow", "day after tomorrow", "the day after tomorrow"]
    
    # TOMORROW keywords = next day (+1 day)
    tomorrow_keywords = ["tomorrow morning", "tomorrow afternoon", "tomorrow evening", "tomorrow night", "tomorrow"]
    
    # TODAY keywords = current date (same day)
    today_keywords = ["tonight", "today", "later today", "this afternoon", 
                      "this evening", "this morning"]
    
    # Smart parsing - check for immediate requests first
    if any(keyword in speech_text.lower() for keyword in immediate_keywords):
        current_time = datetime.now()
        booking_data['pickup_date'] = current_time.strftime("%d/%m/%Y")
        booking_data['pickup_time'] = "ASAP"
        print(f"🚨 IMMEDIATE BOOKING DETECTED: Setting to TODAY ASAP")
    elif any(keyword in speech_text.lower() for keyword in after_tomorrow_keywords):
        day_after_tomorrow = datetime.now() + timedelta(days=2)
        booking_data['pickup_date'] = day_after_tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in tomorrow_keywords):
        tomorrow = datetime.now() + timedelta(days=1)
        booking_data['pickup_date'] = tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in today_keywords):
        today = datetime.now()
        booking_data['pickup_date'] = today.strftime("%d/%m/%Y")
    else:
        # Try to find explicit date formats
        date_patterns = [
            r"(?:date|on)\s+(\d{1,2}/\d{1,2}/\d{4})",
            r"(?:date|on)\s+(\d{1,2}/\d{1,2}/\d{2})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{2})"
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, speech_text, re.IGNORECASE)
            if match:
                booking_data['pickup_date'] = match.group(1).strip()
                break
    
    # Extract time - improved patterns including immediate requests
    time_patterns = [
        r"time\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(quarter\s+past\s+\d{1,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(half\s+past\s+\d{1,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"(?:today|tomorrow|tonight)\s+at\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))"
    ]
    
    # Check for immediate time requests first (overrides specific times)
    immediate_time_keywords = ["right now", "now", "asap", "as soon as possible", "immediately", "straight away"]
    
    if any(keyword in speech_text.lower() for keyword in immediate_time_keywords):
        booking_data['pickup_time'] = "ASAP"
        print(f"🚨 IMMEDIATE TIME DETECTED: Setting to ASAP")
    else:
        # Look for specific times
        for pattern in time_patterns:
            match = re.search(pattern, speech_text, re.IGNORECASE)
            if match:
                time_str = match.group(1).strip()
                # Convert quarter past, half past
                if "quarter past" in time_str:
                    time_str = time_str.replace("quarter past ", "").replace("quarter past", "")
                    hour = time_str.split()[0]
                    ampm = time_str.split()[-1] if len(time_str.split()) > 1 else ""
                    time_str = f"{hour}:15 {ampm}"
                elif "half past" in time_str:
                    time_str = time_str.replace("half past ", "").replace("half past", "")
                    hour = time_str.split()[0]
                    ampm = time_str.split()[-1] if len(time_str.split()) > 1 else ""
                    time_str = f"{hour}:30 {ampm}"
                
                # Fix formatting for times like "9 p.m."
                time_str = time_str.replace('p.m.', 'PM').replace('p.m', 'PM')
                time_str = time_str.replace('a.m.', 'AM').replace('a.m', 'AM')
                
                # Add :00 if no minutes specified
                if ':' not in time_str and any(x in time_str for x in ['AM', 'PM']):
                    time_str = time_str.replace(' AM', ':00 AM').replace(' PM', ':00 PM')
                
                booking_data['pickup_time'] = time_str
                break
    
    return booking_data

def send_booking_to_api(booking_data, caller_number):
    """Send booking to TaxiCaller API or Render endpoint"""
    # First try TaxiCaller if API key is configured
    if TAXICALLER_API_KEY:
        try:
            success, response = send_booking_to_taxicaller(booking_data, caller_number)
            if success:
                return success, response
            else:
                print("⚠️ TaxiCaller failed, falling back to Render endpoint")
        except Exception as e:
            print(f"⚠️ TaxiCaller error: {str(e)}, falling back to Render endpoint")
    
    # Original fallback code to Render endpoint
    try:
        api_data = {
            "customer_name": booking_data.get('name', ''),
            "phone": caller_number,
            "pickup_address": booking_data.get('pickup_address', ''),
            "destination": booking_data.get('destination', ''),
            "pickup_time": booking_data.get('pickup_time', ''),
            "pickup_date": booking_data.get('pickup_date', ''),
            "booking_reference": caller_number.replace('+', '').replace('-', '').replace(' ', ''),
            "service": "taxi",
            "created_via": "ai_ivr",
            "raw_speech": booking_data.get('raw_speech', '')
        }
        
        # Fallback to Render endpoint with reduced timeout
        response = requests.post(
            RENDER_ENDPOINT,
            json=api_data,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ BOOKING SENT TO RENDER: {response.status_code}")
            return True, response.json()
        else:
            print(f"❌ API ERROR: {response.status_code} - {response.text}")
            return False, None
            
    except requests.Timeout:
        print(f"⚠️ API TIMEOUT - but booking was likely received")
        return True, None  # Return success anyway
    except Exception as e:
        print(f"❌ API SEND ERROR: {str(e)}")
        return False, None

def detect_landline_location(caller_number):
    """Detect location from New Zealand landline area codes"""
    try:
        clean_number = caller_number.replace('+64', '').replace(' ', '').replace('-', '')
        
        nz_area_codes = {
            '03': {
                'region': 'South Island',
                'cities': ['Christchurch', 'Dunedin', 'Invercargill', 'Nelson', 'Timaru'],
                'main_city': 'Christchurch',
                'coordinates': (-43.5321, 172.6362)
            },
            '04': {
                'region': 'Wellington Region',
                'cities': ['Wellington', 'Lower Hutt', 'Upper Hutt', 'Porirua', 'Kapiti Coast'],
                'main_city': 'Wellington',
                'coordinates': (-41.2865, 174.7762)
            },
            '06': {
                'region': 'Lower North Island',
                'cities': ['New Plymouth', 'Whanganui', 'Palmerston North', 'Napier', 'Hastings'],
                'main_city': 'Palmerston North',
                'coordinates': (-40.3523, 175.6082)
            },
            '07': {
                'region': 'Central North Island',
                'cities': ['Hamilton', 'Tauranga', 'Rotorua', 'Taupo', 'Thames'],
                'main_city': 'Hamilton',
                'coordinates': (-37.7879, 175.2793)
            },
            '09': {
                'region': 'Auckland Region',
                'cities': ['Auckland', 'North Shore', 'Waitakere', 'Manukau'],
                'main_city': 'Auckland',
                'coordinates': (-36.8485, 174.7633)
            }
        }
        
        for area_code, location_info in nz_area_codes.items():
            if clean_number.startswith(area_code):
                print(f"📞 LANDLINE DETECTED: Area code {area_code}")
                print(f"🏙️ Region: {location_info['region']}")
                print(f"📍 Main city: {location_info['main_city']}")
                
                return {
                    'is_landline': True,
                    'area_code': area_code,
                    'region': location_info['region'],
                    'main_city': location_info['main_city'],
                    'possible_cities': location_info['cities'],
                    'coordinates': location_info['coordinates'],
                    'confidence': 'area_code_based'
                }
        
        if clean_number.startswith('02'):
            print(f"📱 MOBILE NUMBER DETECTED: {caller_number}")
            return {
                'is_landline': False,
                'is_mobile': True,
                'area_code': '02',
                'region': 'Mobile - Location varies',
                'confidence': 'mobile_number'
            }
        
        print(f"❓ UNKNOWN NUMBER FORMAT: {caller_number}")
        return None
        
    except Exception as e:
        print(f"⚠️ Error detecting landline location: {str(e)}")
        return None

def get_caller_location(request_data):
    """Enhanced caller location detection with landline support"""
    try:
        caller_number = request_data.get('From', '')
        
        landline_info = detect_landline_location(caller_number)
        
        if landline_info and landline_info.get('is_landline'):
            location_info = {
                'has_coordinates': True,
                'latitude': landline_info['coordinates'][0],
                'longitude': landline_info['coordinates'][1],
                'city': landline_info['main_city'],
                'region': landline_info['region'],
                'country': 'New Zealand',
                'area_code': landline_info['area_code'],
                'is_landline': True,
                'possible_cities': landline_info['possible_cities'],
                'confidence': 'area_code_landline',
                'formatted_address': f"{landline_info['main_city']}, {landline_info['region']}, New Zealand"
            }
            
            print(f"📞 LANDLINE LOCATION:")
            print(f"   📍 Area Code: {landline_info['area_code']}")
            print(f"   🏙️ Region: {landline_info['region']}")
            print(f"   📌 Main City: {landline_info['main_city']}")
            print(f"   🌍 Coordinates: {location_info['latitude']}, {location_info['longitude']}")
            
            return location_info
        
        elif landline_info and landline_info.get('is_mobile'):
            print(f"📱 MOBILE NUMBER - trying GPS detection...")
        
        caller_country = request_data.get('CallerCountry', '')
        caller_state = request_data.get('CallerState', '')
        caller_city = request_data.get('CallerCity', '')
        caller_zip = request_data.get('CallerZip', '')
        
        caller_lat = request_data.get('CallerLat', '')
        caller_lon = request_data.get('CallerLon', '')
        
        from_city = request_data.get('FromCity', '')
        from_state = request_data.get('FromState', '')
        from_country = request_data.get('FromCountry', '')
        
        location_info = {
            'has_coordinates': bool(caller_lat and caller_lon),
            'latitude': float(caller_lat) if caller_lat else None,
            'longitude': float(caller_lon) if caller_lon else None,
            'city': caller_city or from_city or '',
            'state': caller_state or from_state or '',
            'country': caller_country or from_country or '',
            'zip_code': caller_zip or '',
            'is_landline': False,
            'confidence': 'gps_mobile' if (caller_lat and caller_lon) else 'network_mobile',
            'formatted_address': ''
        }
        
        address_parts = []
        if location_info['city']:
            address_parts.append(location_info['city'])
        if location_info['state']:
            address_parts.append(location_info['state'])
        if location_info['country']:
            address_parts.append(location_info['country'])
        
        location_info['formatted_address'] = ', '.join(address_parts)
        
        print(f"📱 MOBILE LOCATION:")
        print(f"   📱 Has GPS: {location_info['has_coordinates']}")
        if location_info['has_coordinates']:
            print(f"   🌍 Coordinates: {location_info['latitude']}, {location_info['longitude']}")
        print(f"   🏙️ City: {location_info['city']}")
        print(f"   📍 Full: {location_info['formatted_address']}")
        
        return location_info
        
    except Exception as e:
        print(f"⚠️ Error getting caller location: {str(e)}")
        return {
            'has_coordinates': False,
            'latitude': None,
            'longitude': None,
            'city': 'Wellington',
            'state': '',
            'country': 'New Zealand',
            'zip_code': '',
            'is_landline': False,
            'confidence': 'default',
            'formatted_address': 'Wellington, New Zealand'
        }

def validate_wellington_service_area(caller_location, booking_addresses=None):
    """Validate that service request is within Wellington region"""
    
    wellington_service_area = {
        'area_codes': ['04'],
        'region_name': 'Wellington Region',
        'service_cities': [
            'wellington', 'lower hutt', 'upper hutt', 'porirua', 'kapiti coast',
            'paraparaumu', 'waikanae', 'eastbourne', 'petone', 'johnsonville'
        ],
        'coordinates_bounds': {
            'north': -40.8,
            'south': -41.5,
            'west': 174.6,
            'east': 175.2
        }
    }
    
    print(f"🌍 VALIDATING SERVICE AREA...")
    
    if caller_location and caller_location.get('is_landline'):
        area_code = caller_location.get('area_code', '')
        
        if area_code not in wellington_service_area['area_codes']:
            print(f"❌ OUTSIDE SERVICE AREA: Area code {area_code} not in Wellington region")
            return {
                'in_service_area': False,
                'reason': 'outside_wellington_region',
                'caller_region': caller_location.get('region', 'Unknown'),
                'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. I can see you're calling from {caller_location.get('region', 'outside Wellington')}."
            }
    
    if caller_location and caller_location.get('has_coordinates'):
        lat = caller_location.get('latitude')
        lon = caller_location.get('longitude')
        bounds = wellington_service_area['coordinates_bounds']
        
        if not (bounds['south'] <= lat <= bounds['north'] and 
                bounds['west'] <= lon <= bounds['east']):
            print(f"❌ OUTSIDE SERVICE AREA: GPS coordinates {lat}, {lon} not in Wellington region")
            return {
                'in_service_area': False,
                'reason': 'outside_wellington_coordinates',
                'coordinates': (lat, lon),
                'message': "Sorry, Kiwi Cabs operates only in the Wellington region. Your current location appears to be outside our service area."
            }
    
    if caller_location:
        city = caller_location.get('city', '').lower()
        if city and city not in wellington_service_area['service_cities']:
            wellington_variations = ['wellington', 'wgtn', 'welly']
            if not any(var in city for var in wellington_variations):
                print(f"❌ OUTSIDE SERVICE AREA: City '{city}' not in Wellington region")
                return {
                    'in_service_area': False,
                    'reason': 'outside_wellington_city',
                    'caller_city': city,
                    'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. I can see you're calling from {city.title()}."
                }
    
    if booking_addresses:
        for address_type, address in booking_addresses.items():
            if address and not is_wellington_address(address):
                print(f"❌ OUTSIDE SERVICE AREA: {address_type} '{address}' not in Wellington region")
                return {
                    'in_service_area': False,
                    'reason': f'booking_{address_type}_outside_wellington',
                    'problematic_address': address,
                    'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. Your {address_type} address appears to be outside our service area."
                }
    
    print(f"✅ WITHIN SERVICE AREA: Wellington region confirmed")
    return {
        'in_service_area': True,
        'reason': 'wellington_region_confirmed',
        'message': None
    }

def is_wellington_address(address):
    """Enhanced Wellington address validation"""
    if not address:
        return True
    
    address_lower = address.lower()
    
    wellington_keywords = [
        'wellington', 'wgtn', 'welly', 'lower hutt', 'upper hutt', 'hutt valley', 'hutt', 
        'porirua', 'kapiti', 'paraparaumu', 'waikanae', 'otaki', 'eastbourne', 'petone',
        'johnsonville', 'tawa', 'miramar', 'kilbirnie', 'newtown', 'karori',
        'brooklyn', 'island bay', 'kelburn', 'thorndon', 'te aro', 'mount victoria',
        'oriental bay', 'hataitai', 'roseneath', 'mount cook', 'aro valley',
        'wadestown', 'khandallah', 'ngaio', 'crofton downs', 'northland', 'broadmeadows',
        'churton park', 'glenside', 'grenada north', 'grenada village', 'paparangi',
        'woodridge', 'horokiwi', 'alicetown', 'avalon', 'boulcott', 'epuni',
        'gracefield', 'haywards', 'manor park', 'moera', 'naenae', 'stokes valley',
        'taita', 'wainuiomata', 'waterloo', 'woburn', 'belmont', 'brentwood',
        'heretaunga', 'pinehaven', 'silverstream', 'totara park', 'wallaceville',
        'aotea', 'camborne', 'elsdon', 'linden', 'mana', 'paremata', 'plimmerton',
        'pukerua bay', 'raumati', 'titahi bay', 'whitby', 'cannon point', 'paekakariki'
    ]
    
    for keyword in wellington_keywords:
        if keyword in address_lower:
            print(f"✅ WELLINGTON ADDRESS CONFIRMED: '{keyword}' found in '{address}'")
            return True
    
    outside_cities = [
        'auckland', 'christchurch', 'hamilton', 'tauranga', 'dunedin',
        'palmerston north', 'hastings', 'napier', 'rotorua', 'new plymouth',
        'whanganui', 'invercargill', 'nelson', 'timaru', 'whangarei',
        'gisborne', 'blenheim', 'masterton', 'levin', 'feilding',
        'melbourne', 'sydney', 'brisbane', 'perth', 'adelaide'  # Add Australian cities
    ]
    
    for city in outside_cities:
        if city in address_lower:
            print(f"❌ NON-WELLINGTON CITY DETECTED: '{city}' found in '{address}'")
            return False
    
    outside_airports = ['auckland airport', 'akl airport', 'christchurch airport', 'chc airport']
    for airport in outside_airports:
        if airport in address_lower:
            print(f"❌ NON-WELLINGTON AIRPORT: '{airport}' found in '{address}'")
            return False
    
    wellington_landmarks = [
        'airport', 'train station', 'railway station', 'wellington station',
        'interislander', 'ferry terminal', 'parliament', 'beehive',
        'te papa', 'cuba mall', 'botanic garden', 'cable car'
    ]
    
    for landmark in wellington_landmarks:
        if landmark in address_lower:
            print(f"✅ WELLINGTON LANDMARK DETECTED: '{landmark}' in '{address}'")
            return True
    
    print(f"⚠️ UNCLEAR ADDRESS: '{address}' - assuming Wellington region")
    return True

def redirect_to(path):
    """Helper function to create redirect responses"""
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

# Add simple root endpoint for testing
@app.route("/", methods=["GET"])
def index():
    """Simple endpoint to verify service is running"""
    return {
        "status": "running",
        "service": "Kiwi Cabs AI Service",
        "endpoints": [
            "/health",
            "/voice",
            "/menu",
            "/book_with_location",
            "/process_booking",
            "/confirm_booking",
            "/modify_booking",
            "/team",
            "/api/bookings"
        ]
    }, 200

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Kiwi Cabs Booking Service", "version": "2.0"}, 200

@app.route("/voice", methods=["POST"])
def voice():
    """Original greeting with keypad options added"""
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
    """Handle keypad input only"""
    digits = request.form.get("Digits", "")
    
    if digits == "1":
        print(f"📞 KEYPAD: User pressed 1 - NEW BOOKING")
        return redirect_to("/book_with_location")
    elif digits == "2":
        print(f"📞 KEYPAD: User pressed 2 - MODIFY BOOKING")
        return redirect_to("/modify_booking")
    elif digits == "3":
        print(f"📞 KEYPAD: User pressed 3 - TRANSFER TO TEAM")
        return redirect_to("/team")
    else:
        # Invalid input or timeout - repeat menu
        return redirect_to("/voice")

@app.route("/book_with_location", methods=["POST"])
def book_with_location():
    """Start booking process with separate Say and Gather and I am listening prompt"""
    request_data = dict(request.form)
    
    caller_location = get_caller_location(request_data)
    call_sid = request.form.get("CallSid", "")
    
    validation_result = validate_wellington_service_area(caller_location)
    
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {}
    user_sessions[call_sid]['caller_location'] = caller_location
    user_sessions[call_sid]['validation_result'] = validation_result
    
    if not validation_result['in_service_area']:
        print(f"🚫 CALL OUTSIDE SERVICE AREA: {validation_result['reason']}")
        return redirect_to("/outside_service_area")
    
    print(f"✅ CALL WITHIN WELLINGTON SERVICE AREA - proceeding with booking")
    
    # Separate Say and Gather with "I am listening" prompt and reduced speechTimeout
    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I'll help you book your taxi.
        Please tell me your name, pickup address, destination, date, and time.
        For example, you can say:
        My name is James Smith, from 63 Hobart Street to Wellington Airport, tomorrow at 9 AM.
        <break time="0.5s"/>
        I am listening.
    </Say>
    <Gather input="speech" 
            action="/process_booking" 
            method="POST" 
            timeout="20" 
            language="en-NZ" 
            speechTimeout="1" 
            finishOnKey="" 
            enhanced="true">
        <Say></Say>
    </Gather>
</Response>"""
    return Response(response_xml, mimetype="text/xml")

@app.route("/outside_service_area", methods=["POST"])
def outside_service_area():
    """Handle calls from outside Wellington service area"""
    call_sid = request.form.get("CallSid", "")
    session_data = user_sessions.get(call_sid, {})
    validation_result = session_data.get('validation_result', {})
    
    caller_region = validation_result.get('caller_region', 'your area')
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Kiwi Cabs operates only in the Wellington region. 
        I can see you're calling from {caller_region}.
        For taxi services in your area, I recommend searching online for local taxi companies.
        Thanks for calling, and have a great day!
    </Say>
    <Hangup/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_booking", methods=["POST"])
def process_booking():
    """Process new booking details with Google Speech fallback"""
    speech_data = request.form.get("SpeechResult", "")
    confidence = float(request.form.get("Confidence", "0"))
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🎯 TWILIO TRANSCRIPTION: '{speech_data}' (Confidence: {confidence})")
    print(f"🔍 DEBUG: Entering process_booking function")
    print(f"🔍 DEBUG: Call SID: {call_sid}")
    
    # If Twilio confidence is too low or no speech detected, try recording if Google is available
    if GOOGLE_SPEECH_AVAILABLE and (confidence < 0.8 or not speech_data.strip()):
        print(f"⚠️ Low confidence ({confidence}) - switching to recording for Google Speech")
        
        # Store what we have so far
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['low_confidence'] = True
        user_sessions[call_sid]['caller_number'] = caller_number
        
        # Record the audio for Google Speech processing
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please repeat your booking details.
    </Say>
    <Record action="/process_booking_with_google" 
            method="POST" 
            maxLength="30" 
            timeout="5"
            speechTimeout="3"
            finishOnKey="#"
            playBeep="false"/>
</Response>"""
        return Response(response, mimetype="text/xml")
    
    # If Google is not available or Twilio confidence is good, continue with normal processing
    print(f"✅ Processing with Twilio transcription")
    
    # GET EXISTING DATA from session if available
    existing_data = {}
    if call_sid in user_sessions:
        existing_data = user_sessions[call_sid].get('partial_booking', {})
        print(f"📝 EXISTING DATA: {existing_data}")
    
    # Parse the speech into structured booking data
    booking_data = parse_booking_speech(speech_data)
    
    # MERGE new data with existing data - keep existing if new is empty
    merged_booking = {
        'name': booking_data['name'] or existing_data.get('name', ''),
        'pickup_address': booking_data['pickup_address'] or existing_data.get('pickup_address', ''),
        'destination': booking_data['destination'] or existing_data.get('destination', ''),
        'pickup_time': booking_data['pickup_time'] or existing_data.get('pickup_time', ''),
        'pickup_date': booking_data['pickup_date'] or existing_data.get('pickup_date', ''),
        'raw_speech': f"{existing_data.get('raw_speech', '')} {speech_data}".strip()
    }
    
    # Store merged data back in session
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {}
    user_sessions[call_sid]['partial_booking'] = merged_booking
    user_sessions[call_sid]['caller_number'] = caller_number
    
    print(f"📋 MERGED BOOKING DATA:")
    print(f"   👤 Name: {merged_booking['name']}")
    print(f"   📍 Pickup: {merged_booking['pickup_address']}")
    print(f"   🎯 Destination: {merged_booking['destination']}")
    print(f"   🕐 Time: {merged_booking['pickup_time']}")
    print(f"   📅 Date: {merged_booking['pickup_date']}")
    
    # Use merged_booking for all further processing
    booking_data = merged_booking
    
    # COMPREHENSIVE VALIDATION: Check ALL required fields individually
    missing_items = []
    missing_prompts = []
    
    # Check NAME - be more lenient
    if not booking_data['name'].strip() or len(booking_data['name'].strip()) < 2:
        missing_items.append("name")
        missing_prompts.append("your name")
    
    # Check PICKUP ADDRESS - be more lenient
    if not booking_data['pickup_address'].strip() or len(booking_data['pickup_address'].strip()) < 5:
        missing_items.append("pickup address")
        missing_prompts.append("your pickup address")
    
    # Check DESTINATION - be more lenient
    if not booking_data['destination'].strip() or len(booking_data['destination'].strip()) < 3:
        missing_items.append("destination")
        missing_prompts.append("your destination or drop-off location")
    
    # Check for vague destinations - be more lenient
    vague_destinations = ['there', 'here', 'that place', 'you know', 'same place', 'usual']
    destination_lower = booking_data['destination'].lower().strip()
    
    # Only flag as vague if it's REALLY vague (not common places like "work", "home")
    if booking_data['destination'].strip() and any(vague == destination_lower for vague in vague_destinations):
        missing_items.append("specific destination")
        missing_prompts.append("a more specific destination address or location name")
    
    # If ANY required field is missing, ask specifically for what's missing
    if missing_items:
        missing_text = ", ".join(missing_prompts[:-1])
        if len(missing_prompts) > 1:
            missing_text += f" and {missing_prompts[-1]}"
        else:
            missing_text = missing_prompts[0]
        
        print(f"❌ MISSING REQUIRED FIELDS: {missing_items}")
        print(f"📝 ASKING FOR: {missing_text}")
        
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I need {missing_text} to complete your booking.
        Please provide the missing information.
        <break time="0.5s"/>
        I am listening.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="20" language="en-NZ" speechTimeout="1" finishOnKey="" enhanced="true">
        <Say></Say>
    </Gather>
</Response>""", mimetype="text/xml")

    # ADDITIONAL: Check for reasonable pickup address (not just numbers)
    pickup_lower = booking_data['pickup_address'].lower().strip()
    if len(pickup_lower) < 5 or pickup_lower.isdigit():
        print(f"❌ INCOMPLETE PICKUP ADDRESS: '{booking_data['pickup_address']}'")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I need your complete pickup address including street name and suburb.
        Please tell me your full pickup address.
        <break time="0.5s"/>
        I am listening.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="20" language="en-NZ" speechTimeout="2" finishOnKey="" enhanced="true">
        <Say></Say>
    </Gather>
</Response>""", mimetype="text/xml")

    # FINAL VALIDATION: Ensure destination is specific enough
    if len(booking_data['destination'].strip()) < 5:
        print(f"❌ DESTINATION TOO SHORT: '{booking_data['destination']}'")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I need a more specific destination.
        Please tell me the full address or location name where you want to go.
        <break time="0.5s"/>
        I am listening.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="20" language="en-NZ" speechTimeout="2" finishOnKey="" enhanced="true">
        <Say></Say>
    </Gather>
</Response>""", mimetype="text/xml")

    # Check if pickup is from outside Wellington - reject these bookings
    pickup_address = booking_data.get('pickup_address', '').lower()
    outside_pickup_keywords = ['melbourne', 'sydney', 'auckland', 'christchurch', 'hamilton']
    
    if any(keyword in pickup_address for keyword in outside_pickup_keywords):
        outside_city = next(keyword for keyword in outside_pickup_keywords if keyword in pickup_address)
        print(f"🚫 OUTSIDE PICKUP DETECTED - rejecting booking from: {pickup_address}")
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Kiwi Cabs operates only in the Wellington region. 
        I can see you're requesting pickup from {outside_city.title()}, which is outside our service area.
        Thank you for calling!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")

    # Check if pickup is from ANY airport variation - reject these bookings
    airport_pickup_keywords = [
        'airport', 'wellington airport', 'wlg airport', 'terminal', 
        'domestic airport', 'international airport', 'steward duff', 
        'stewart duff', 'steward duff driver airport', 'stewart duff driver airport'
    ]
    
    if any(keyword in pickup_address for keyword in airport_pickup_keywords):
        print(f"✈️ AIRPORT PICKUP DETECTED - rejecting booking from: {pickup_address}")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        You don't need to book a taxi from the airport as we have taxis waiting at the airport rank.
        Thank you for calling Kiwi Cabs and goodbye!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")

    # Validate Wellington addresses
    session_data = user_sessions.get(call_sid, {})
    booking_addresses = {
        'pickup': booking_data['pickup_address'],
        'destination': booking_data['destination']
    }
    
    validation_result = validate_wellington_service_area(
        session_data.get('caller_location'), 
        booking_addresses
    )
    
    if not validation_result['in_service_area']:
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {validation_result['message']}
        Thanks for calling!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    
    # Store booking data in session for confirmation - MOVED TO TOP
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {}
    user_sessions[call_sid]['pending_booking'] = booking_data
    user_sessions[call_sid]['caller_number'] = caller_number

    # REMOVE OLD VALIDATION - replaced with comprehensive validation above
    # All validation is now handled by the comprehensive check above

    # Create clean confirmation message - ALWAYS ask for confirmation
    confirmation_parts = []
    
    if booking_data['name']:
        confirmation_parts.append(booking_data['name'])
    
    if booking_data['pickup_address']:
        confirmation_parts.append(f"from {booking_data['pickup_address']}")
    
    if booking_data['destination']:
        confirmation_parts.append(f"to {booking_data['destination']}")
    
    if booking_data['pickup_date']:
        confirmation_parts.append(booking_data['pickup_date'])
    
    if booking_data['pickup_time']:
        confirmation_parts.append(booking_data['pickup_time'])
    
    # Join all parts with commas
    confirmation_text = ", ".join(confirmation_parts) if confirmation_parts else "incomplete booking details"
    
    print(f"🔍 DEBUG: Creating confirmation response")
    print(f"🔍 DEBUG: confirmation_parts = {confirmation_parts}")
    print(f"🔍 DEBUG: confirmation_text = '{confirmation_text}'")
    print(f"🔍 DEBUG: About to create TwiML response")
    print(f"❓ ASKING FOR CONFIRMATION: {confirmation_text}")
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/confirm_booking" input="speech" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Let me confirm your booking: {confirmation_text}.
            Please say YES to confirm this booking, or NO to make changes.
        </Say>
    </Gather>
    <Redirect>/process_booking</Redirect>
</Response>"""
    
    return Response(response, mimetype="text/xml")
import requests
import json
from flask import Flask, request, Response, jsonify
from datetime import datetime, timedelta
import re
import urllib.parse
import time
import base64

# Try to import Google Cloud Speech, but make it optional
try:
    from google.cloud import speech
    from google.oauth2 import service_account
    GOOGLE_SPEECH_AVAILABLE = True
except ImportError:
    print("⚠️ Google Cloud Speech not available - will use Twilio transcription only")
    GOOGLE_SPEECH_AVAILABLE = False

app = Flask(__name__)

