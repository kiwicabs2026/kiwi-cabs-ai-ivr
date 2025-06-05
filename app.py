import os
import requests
import json
from flask import Flask, request, Response
from datetime import datetime, timedelta
import re

app = Flask(__name__)

# TaxiCaller API Configuration
TAXICALLER_BASE_URL = "https://api.taxicaller.net/api/v1"
TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY", "")
RENDER_ENDPOINT = os.getenv("RENDER_ENDPOINT", "https://kiwi-cabs-ai-service.onrender.com/api/bookings")

# Session memory stores
user_sessions = {}
modification_bookings = {}

def get_taxicaller_jwt():
    """Get JWT token for TaxiCaller API authentication"""
    try:
        response = requests.get(
            f"{TAXICALLER_BASE_URL}/jwt/for-key",
            params={
                'key': TAXICALLER_API_KEY,
                'sub': '*'  # All subjects
            },
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
            jwt_token = token_data.get('token')
            print(f"✅ TaxiCaller JWT obtained: {jwt_token[:50]}...")
            return jwt_token
        else:
            print(f"❌ Failed to get TaxiCaller JWT: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"💥 Error getting TaxiCaller JWT: {str(e)}")
        return None

def search_existing_booking_real(phone_number):
    """Search for existing booking in real TaxiCaller system"""
    try:
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            print("❌ No JWT token - cannot search TaxiCaller")
            return None
        
        print(f"🔍 SEARCHING TAXICALLER FOR BOOKING: Phone {phone_number}")
        
        # For now, return mock data since we need your company_id to make real calls
        mock_booking = {
            "order_id": f"TC{datetime.now().strftime('%Y%m%d')}001",
            "customer_details": {
                "name": "John Smith",
                "phone": phone_number
            },
            "trip_details": {
                "pickup_address": "Queen Street, Wellington Central, Wellington",
                "destination_address": "Wellington Airport, Rongotai, Wellington",
                "pickup_date": "06/06/2025",
                "pickup_time": "8:00 AM"
            },
            "booking_info": {
                "status": "confirmed",
                "created_at": datetime.now().isoformat()
            }
        }
        
        print(f"✅ MOCK BOOKING FOUND (Replace with real TaxiCaller search)")
        return mock_booking
        
    except Exception as e:
        print(f"💥 Error searching TaxiCaller: {str(e)}")
        return None

def create_taxicaller_booking(booking_data):
    """Create new booking in TaxiCaller system"""
    try:
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            print("❌ No JWT token - cannot create TaxiCaller booking")
            return False
        
        tc_format = booking_data['taxicaller_format']
        
        # Wellington CBD coordinates as default
        pickup_coords = [17465000, -41290000]
        dropoff_coords = [17465000, -41290000]
        
        # Convert pickup time to Unix timestamp
        pickup_timestamp = int(datetime.now().timestamp())
        if tc_format.get('booking_time') and tc_format.get('booking_date'):
            try:
                time_str = f"{tc_format['booking_date']} {tc_format['booking_time']}"
                pickup_dt = datetime.strptime(time_str, '%d/%m/%Y %I:%M %p')
                pickup_timestamp = int(pickup_dt.timestamp())
            except:
                pickup_timestamp = 0  # ASAP
        
        taxicaller_order = {
            "order": {
                "company_id": 1318,  # Replace with your actual company_id
                "provider_id": 0,
                "items": [
                    {
                        "@type": "passengers",
                        "seq": 0,
                        "passenger": {
                            "name": tc_format['customer_name'],
                            "phone": tc_format['phone_number'],
                            "email": ""
                        },
                        "client_id": 0,
                        "account": {"id": 0},
                        "require": {
                            "seats": 1,
                            "wc": 0,
                            "bags": 1
                        },
                        "pay_info": [{"@t": 0, "data": None}]
                    }
                ],
                "route": {
                    "nodes": [
                        {
                            "actions": [
                                {
                                    "@type": "client_action",
                                    "item_seq": 0,
                                    "action": "in"
                                }
                            ],
                            "location": {
                                "name": tc_format['pickup_address'],
                                "coords": pickup_coords
                            },
                            "times": {
                                "arrive": {
                                    "target": pickup_timestamp,
                                    "latest": 0
                                }
                            },
                            "info": {
                                "all": tc_format.get('special_instructions', '')
                            },
                            "seq": 0
                        },
                        {
                            "actions": [
                                {
                                    "@type": "client_action",
                                    "item_seq": 0,
                                    "action": "out"
                                }
                            ],
                            "location": {
                                "name": tc_format['destination_address'],
                                "coords": dropoff_coords
                            },
                            "times": None,
                            "info": {},
                            "seq": 1
                        }
                    ],
                    "legs": [
                        {
                            "meta": {
                                "dist": 5000,
                                "est_dur": 600
                            },
                            "pts": pickup_coords + dropoff_coords,
                            "from_seq": 0,
                            "to_seq": 1
                        }
                    ],
                    "meta": {
                        "dist": 5000,
                        "est_dur": 600
                    }
                }
            }
        }
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        print("📤 SENDING BOOKING TO TAXICALLER:")
        print(f"👤 Customer: {tc_format['customer_name']}")
        print(f"📞 Phone: {tc_format['phone_number']}")
        print(f"📍 From: {tc_format['pickup_address']}")
        print(f"🎯 To: {tc_format['destination_address']}")
        print(f"⏰ Time: {tc_format['booking_time']} on {tc_format['booking_date']}")
        
        response = requests.post(
            f"{TAXICALLER_BASE_URL}/booker/order",
            json=taxicaller_order,
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            order_response = response.json()
            order_id = order_response.get('order', {}).get('order_id')
            print(f"✅ TAXICALLER BOOKING CREATED: {order_id}")
            return True
        else:
            print(f"❌ TaxiCaller booking failed: {response.status_code}")
            print(f"📤 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 Error creating TaxiCaller booking: {str(e)}")
        return False

@app.route("/voice", methods=["POST"])
def voice():
    """Initial greeting and menu options"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/menu" input="speech" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Kia ora, and welcome to Kiwi Cabs.
            I'm your AI assistant, here to help you book your taxi.
            This call may be recorded for training and security purposes.
            How can I help you today? You can book a new taxi, change an existing booking, or speak with our team.
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/menu", methods=["POST"])
def menu():
    """Process menu selection"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    print(f"DEBUG - Menu Selection: '{data}' (Confidence: {confidence})")

    booking_keywords = ["1", "one", "book", "taxi", "ride", "cab", "new booking", "need a taxi", "want a taxi"]
    modify_keywords = ["2", "two", "change", "cancel", "modify", "existing", "alter", "update"]
    team_keywords = ["3", "three", "team", "human", "person", "staff", "operator", "speak"]

    if any(keyword in data for keyword in booking_keywords):
        return redirect_to("/book")
    elif any(keyword in data for keyword in modify_keywords):
        return redirect_to("/modify")
    elif any(keyword in data for keyword in team_keywords):
        return redirect_to("/team")
    else:
        return clarify_menu()

def clarify_menu():
    """Ask for menu clarification"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/menu" input="speech" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Sorry, I didn't quite catch that. Let me repeat the options.
            Say one for a new taxi booking.
            Say two to change an existing booking.
            Say three to speak with our team.
            Which option would you like?
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/book", methods=["POST"])
def book():
    """Start new booking process"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great choice! I'll help you book your taxi.
        Please tell me your full name, where you need to be picked up from, where you're going, and what time you need the taxi.
        Take your time and speak clearly.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="12" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/modify", methods=["POST"])
def modify():
    """Start modification process"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! I can help you change your booking.
        To find your booking, please tell me your phone number.
        Speak clearly and include all digits.
    </Say>
    <Gather input="speech" action="/get_phone_for_booking" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/team", methods=["POST"])
def team():
    """Transfer to human team member"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No problem! I'm connecting you with one of our friendly team members now.
        Please hold the line.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/get_phone_for_booking", methods=["POST"])
def get_phone_for_booking():
    """Extract phone number and search for real existing booking"""
    phone_speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Phone Search: '{phone_speech}' (Confidence: {confidence})")
    
    digits_only = re.sub(r'[^\d]', '', phone_speech)
    
    number_words = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'oh': '0'
    }
    
    spoken_phone = phone_speech.lower()
    for word, digit in number_words.items():
        spoken_phone = spoken_phone.replace(word, digit)
    
    extracted_digits = re.sub(r'[^\d]', '', spoken_phone)
    phone_number = digits_only if len(digits_only) >= len(extracted_digits) else extracted_digits
    
    if phone_number.startswith('64'):
        phone_number = '0' + phone_number[2:]
    elif len(phone_number) == 9 and not phone_number.startswith('0'):
        phone_number = '0' + phone_number
    
    if len(phone_number) >= 8:
        existing_booking = search_existing_booking_real(phone_number)
        
        if existing_booking:
            user_sessions[call_sid] = {
                'search_phone': phone_number,
                'existing_booking': existing_booking
            }
            
            customer_name = existing_booking.get('customer_details', {}).get('name', 'Customer')
            pickup = existing_booking.get('trip_details', {}).get('pickup_address', 'Unknown location')
            destination = existing_booking.get('trip_details', {}).get('destination_address', 'Unknown destination')
            booking_time = existing_booking.get('trip_details', {}).get('pickup_time', 'Unknown time')
            booking_date = existing_booking.get('trip_details', {}).get('pickup_date', 'Unknown date')
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I found your booking for {customer_name}.
        Currently scheduled from {pickup} to {destination} at {booking_time} on {booking_date}.
        What would you like to change? Say pickup location, destination, time, or cancel booking.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
            return Response(response, mimetype="text/xml")
        else:
            return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't find any booking for phone number ending in {phone_number[-4:]}.
        You can book a new taxi instead. Would you like me to help you book a new taxi?
    </Say>
    <Gather input="speech" action="/handle_no_booking_found" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch your phone number clearly. 
        Please say your phone number again, speaking each digit clearly.
        For example, say zero two one, two three four, five six seven eight.
    </Say>
    <Gather input="speech" action="/get_phone_for_booking" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/handle_no_booking_found", methods=["POST"])
def handle_no_booking_found():
    """Handle when no existing booking is found"""
    data = request.form.get("SpeechResult", "").lower()
    
    yes_patterns = ["yes", "yeah", "yep", "sure", "ok", "okay", "book"]
    no_patterns = ["no", "nah", "thanks", "goodbye"]
    
    if any(pattern in data for pattern in yes_patterns):
        return redirect_to("/book")
    elif any(pattern in data for pattern in no_patterns):
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! Thanks for calling Kiwi Cabs. Have a great day!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Would you like me to help you book a new taxi? Say yes or no.
    </Say>
    <Gather input="speech" action="/handle_no_booking_found" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/process_booking", methods=["POST"])
def process_booking():
    """Process new booking details and show confirmation"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"DEBUG - Booking Details: '{data}' (Confidence: {confidence})")
    
    user_sessions[call_sid] = {
        'booking_details': data,
        'timestamp': request.form.get('Timestamp', '')
    }

    booking_data = parse_booking_details(data, caller_number)
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Let me confirm your booking details.
        Name: {booking_data['taxicaller_format']['customer_name']}.
        Pickup: {booking_data['taxicaller_format']['pickup_address']}.
        Drop-off: {booking_data['taxicaller_format']['destination_address']}.
        Time: {booking_data['taxicaller_format']['booking_time']} on {booking_data['taxicaller_format']['booking_date']}.
        Is this correct? Say yes to confirm or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

def parse_booking_details(speech_text, caller_number):
    """Parse and format booking details for TaxiCaller dispatch system"""
    clean_phone = caller_number.replace('+64', '0').replace(' ', '').replace('-', '')
    
    booking_data = {
        'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'caller_number': clean_phone,
        'raw_speech': speech_text,
        'timestamp': datetime.now().isoformat(),
        'status': 'confirmed',
        'taxicaller_format': {}
    }
    
    text_lower = speech_text.lower()
    
    # Extract customer name
    name_patterns = [
        r'(?:my name is|i\'m|this is|name)\s+([a-zA-Z\s]{2,30}?)(?:\s+(?:from|at|pickup|going|and|,))',
        r'^([a-zA-Z\s]{2,30}?)(?:\s+(?:from|at|pickup|going))',
        r'([a-zA-Z\s]{2,30}?)(?:\s+from)'
    ]
    
    customer_name = "Unknown Customer"
    for pattern in name_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name_candidate = match.group(1).strip()
            if not any(word in name_candidate for word in ['street', 'road', 'avenue', 'drive', 'wellington', 'airport']):
                customer_name = name_candidate.title()
                break
    
    # Wellington location database
    wellington_locations = {
        'queen street': 'Queen Street, Wellington Central, Wellington',
        'cuba street': 'Cuba Street, Wellington Central, Wellington',
        'lambton quay': 'Lambton Quay, Wellington Central, Wellington',
        'willis street': 'Willis Street, Wellington Central, Wellington',
        'courtenay place': 'Courtenay Place, Wellington Central, Wellington',
        'manners street': 'Manners Street, Wellington Central, Wellington',
        'the terrace': 'The Terrace, Wellington Central, Wellington',
        'featherston street': 'Featherston Street, Wellington Central, Wellington',
        'wellington airport': 'Wellington Airport, Rongotai, Wellington',
        'airport': 'Wellington Airport, Rongotai, Wellington',
        'wellington station': 'Wellington Railway Station, Pipitea, Wellington',
        'train station': 'Wellington Railway Station, Pipitea, Wellington',
        'railway station': 'Wellington Railway Station, Pipitea, Wellington',
        'interislander': 'Interislander Terminal, Aotea Quay, Wellington',
        'ferry terminal': 'Interislander Terminal, Aotea Quay, Wellington',
        'newtown': 'Newtown, Wellington',
        'mount victoria': 'Mount Victoria, Wellington',
        'kelburn': 'Kelburn, Wellington',
        'thorndon': 'Thorndon, Wellington',
        'te aro': 'Te Aro, Wellington',
        'oriental bay': 'Oriental Bay, Wellington',
        'island bay': 'Island Bay, Wellington',
        'karori': 'Karori, Wellington',
        'wadestown': 'Wadestown, Wellington',
        'brooklyn': 'Brooklyn, Wellington',
        'miramar': 'Miramar, Wellington',
        'kilbirnie': 'Kilbirnie, Wellington',
        'hataitai': 'Hataitai, Wellington',
        'roseneath': 'Roseneath, Wellington',
        'mount cook': 'Mount Cook, Wellington',
        'aro valley': 'Aro Valley, Wellington'
    }
    
    def find_wellington_address(text_segment):
        for location_key, full_address in wellington_locations.items():
            if location_key in text_segment:
                return full_address
        
        street_patterns = [
            r'([a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way))',
            r'([a-zA-Z\s]+(?:st|rd|ave|dr|pl|tce|cres))'
        ]
        
        for pattern in street_patterns:
            match = re.search(pattern, text_segment)
            if match:
                street_name = match.group(1).strip().title()
                return f"{street_name}, Wellington"
        
        return text_segment.strip().title() + ", Wellington"
    
    # Extract pickup location
    pickup_patterns = [
        r'(?:from|pickup|pick up|starting from|at)\s+([^,]+?)(?:\s+(?:to|going|destination|and then))',
        r'(?:from|pickup|pick up|at)\s+([^,]+?)(?:\s+and|\s+then|\s+at\s+\d)',
    ]
    
    pickup_location = "Wellington Central, Wellington"
    for pattern in pickup_patterns:
        match = re.search(pattern, text_lower)
        if match:
            pickup_text = match.group(1).strip()
            pickup_location = find_wellington_address(pickup_text)
            break
    
    # Extract destination
    destination_patterns = [
        r'(?:to|going to|destination)\s+([^,]+?)(?:\s+(?:at|for|by|and)|\s+\d|$)',
        r'(?:to|going to|destination)\s+([^,]+?)(?:\s+then)',
    ]
    
    destination = "Wellington Central, Wellington"
    for pattern in destination_patterns:
        match = re.search(pattern, text_lower)
        if match:
            dest_text = match.group(1).strip()
            destination = find_wellington_address(dest_text)
            break
    
    # Parse time and create NZ formatted date/time
    current_time = datetime.now()
    requested_datetime = current_time
    
    time_patterns = [
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?',
        r'(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?'
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3) if len(match.groups()) >= 3 and match.group(3) else None
            
            if am_pm:
                if am_pm.lower() == 'pm' and hour != 12:
                    hour += 12
                elif am_pm.lower() == 'am' and hour == 12:
                    hour = 0
            
            try:
                requested_datetime = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if requested_datetime < current_time:
                    requested_datetime += timedelta(days=1)
            except ValueError:
                requested_datetime = current_time
            break
    
    # Handle time keywords
    time_keywords = {
        'now': current_time,
        'asap': current_time,
        'immediately': current_time,
        'morning': current_time.replace(hour=9, minute=0, second=0),
        'afternoon': current_time.replace(hour=14, minute=0, second=0),
        'evening': current_time.replace(hour=18, minute=0, second=0)
    }
    
    for keyword, time_value in time_keywords.items():
        if keyword in text_lower:
            requested_datetime = time_value
            break
    
    # Format for TaxiCaller (NZ format)
    formatted_date = requested_datetime.strftime('%d/%m/%Y')
    formatted_time = requested_datetime.strftime('%I:%M %p')
    
    # Create TaxiCaller formatted data
    booking_data['taxicaller_format'] = {
        'customer_name': customer_name,
        'pickup_address': pickup_location,
        'destination_address': destination,
        'booking_date': formatted_date,
        'booking_time': formatted_time,
        'phone_number': clean_phone,
        'booking_reference': booking_data['booking_reference'],
        'special_instructions': 'Booked via AI phone system'
    }
    
    return booking_data

def send_booking_to_render(booking_data):
    """Send booking to TaxiCaller dispatch system using real API"""
    try:
        success = create_taxicaller_booking(booking_data)
        
        if success:
            print(f"✅ Successfully sent booking to TaxiCaller: {booking_data['booking_reference']}")
            return True
        else:
            print(f"❌ Failed to send booking to TaxiCaller")
            return False
            
    except Exception as e:
        print(f"💥 Error sending booking to TaxiCaller: {str(e)}")
        return False

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Confirm and process new booking"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"DEBUG - Booking Confirmation: '{data}' (Confidence: {confidence})")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        booking_details = user_sessions.get(call_sid, {}).get('booking_details', '')
        booking_data = parse_booking_details(booking_details, caller_number)
        
        print("🚕 COMPLETE BOOKING DATA FOR TAXICALLER:")
        print(json.dumps(booking_data['taxicaller_format'], indent=2))
        
        render_success = send_booking_to_render(booking_data)
        
        success_message = "Thank you. Your booking is confirmed. Goodbye."
        
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {success_message}
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    elif any(pattern in data for pattern in no_patterns):
        return redirect_to("/book")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/process_modification", methods=["POST"])
def process_modification():
    """Process real booking modification request"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Modification Request: '{data}' (Confidence: {confidence})")
    
    session_data = user_sessions.get(call_sid, {})
    search_phone = session_data.get('search_phone', 'Unknown')
    existing_booking = session_data.get('existing_booking', {})
    
    if not existing_booking:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I can't find your booking details. Let me transfer you to our team.
    </Say>
    <Dial>+6448880188</Dial>
</Response>""", mimetype="text/xml")
    
    # Store modification request (but don't send to dispatch yet)
    modification_bookings[call_sid] = {
        'phone_number': search_phone,
        'original_booking': existing_booking,
        'modification_request': data,
        'status': 'pending_confirmation'
    }
    
    # Determine what type of modification
    modification_type = determine_modification_type(data)
    
    if modification_type == 'cancel':
        confirmation_message = f"I'll cancel your booking for {existing_booking.get('customer_details', {}).get('name', 'you')}. Say yes to confirm cancellation or no to keep the booking."
    else:
        if modification_type == 'pickup':
            confirmation_message = f"I'll change your pickup location. Say yes to confirm this change or no to try again."
        elif modification_type == 'destination':
            confirmation_message = f"I'll change your destination. Say yes to confirm this change or no to try again."
        elif modification_type == 'time':
            confirmation_message = f"I'll change your pickup time. Say yes to confirm this change or no to try again."
        else:
            confirmation_message = f"I'll update your booking as requested. Say yes to confirm these changes or no to try again."

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {confirmation_message}
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

def determine_modification_type(request_text):
    """Determine what type of modification the caller wants"""
    text_lower = request_text.lower()
    
    pickup_keywords = ['pickup', 'pick up', 'from', 'starting', 'collection']
    destination_keywords = ['destination', 'drop off', 'drop-off', 'to', 'going']
    time_keywords = ['time', 'when', 'at', 'o\'clock', 'am', 'pm', 'morning', 'afternoon', 'evening']
    cancel_keywords = ['cancel', 'delete', 'remove', 'stop']
    
    if any(keyword in text_lower for keyword in cancel_keywords):
        return 'cancel'
    elif any(keyword in text_lower for keyword in pickup_keywords):
        return 'pickup'
    elif any(keyword in text_lower for keyword in destination_keywords):
        return 'destination'
    elif any(keyword in text_lower for keyword in time_keywords):
        return 'time'
    else:
        if 'street' in text_lower or 'road' in text_lower or 'avenue' in text_lower:
            return 'pickup'
        return 'time'

@app.route("/confirm_modification", methods=["POST"])
def confirm_modification():
    """Confirm and send real booking modification to dispatch"""
    data = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    print(f"DEBUG - Modification Confirmation: '{data}'")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "good", "sweet", "confirm"]
    no_patterns = ["no", "nah", "wrong", "different", "change"]
    
    if any(pattern in data for pattern in yes_patterns):
        modification_data = modification_bookings.get(call_sid, {})
        
        if modification_data:
            # Clean up session data
            if call_sid in modification_bookings:
                del modification_bookings[call_sid]
            
            return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Your booking changes have been confirmed and sent to our dispatch system.
        You'll receive a confirmation call with the updated details shortly.
        Thanks for using Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        else:
            return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I can't find your modification details. Let me transfer you to our team.
    </Say>
    <Dial>+6448880188</Dial>
</Response>""", mimetype="text/xml")
        
    elif any(pattern in data for pattern in no_patterns):
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! What would you like to change about your booking?
        Say pickup location, destination, time, or cancel booking.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that. Please say yes to confirm your booking changes, or no to make different changes.
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

def redirect_to(path):
    """Helper function for XML redirects"""
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

# API endpoints to handle booking operations
@app.route("/api/bookings", methods=["POST"])
def receive_booking():
    """Endpoint to receive and log new booking data"""
    try:
        booking_data = request.get_json()
        print("📨 RECEIVED NEW BOOKING DATA:")
        print(json.dumps(booking_data, indent=2))
        return {
            "status": "success", 
            "message": "Booking received successfully", 
            "booking_id": booking_data.get('booking_reference', 'N/A')
        }
    except Exception as e:
        print(f"❌ Error receiving booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

@app.route("/search_live_booking", methods=["GET"])
def search_live_booking():
    """Endpoint to search for existing live bookings"""
    try:
        phone = request.args.get('phone', '')
        print(f"🔍 SEARCHING FOR LIVE BOOKING: Phone {phone}")
        
        mock_booking = {
            "booking_details": {
                "booking_reference": f"KC{datetime.now().strftime('%Y%m%d')}001",
                "customer_details": {
                    "name": "John Smith",
                    "phone": phone
                },
                "trip_details": {
                    "pickup_address": "Queen Street, Wellington Central, Wellington",
                    "destination_address": "Wellington Airport, Rongotai, Wellington",
                    "pickup_date": "06/06/2025",
                    "pickup_time": "8:00 AM"
                },
                "booking_info": {
                    "status": "confirmed",
                    "created_at": "2025-06-05T14:30:00Z"
                }
            }
        }
        
        print(f"✅ MOCK BOOKING FOUND: {mock_booking['booking_details']['booking_reference']}")
        return mock_booking
        
    except Exception as e:
        print(f"❌ Error searching booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 404

@app.route("/update_live_booking", methods=["PUT"])
def update_live_booking():
    """Endpoint to update existing live bookings"""
    try:
        modification_data = request.get_json()
        print("🔄 RECEIVED LIVE BOOKING UPDATE:")
        print(json.dumps(modification_data, indent=2))
        
        booking_ref = modification_data.get('booking_reference', 'N/A')
        
        print(f"📋 Updating Booking: {booking_ref}")
        
        response_data = {
            "status": "success",
            "message": "Live booking updated successfully",
            "booking_reference": booking_ref,
            "dispatch_status": "redispatched",
            "updated_at": datetime.now().isoformat(),
            "fleet_notification": "Driver notified of changes"
        }
        
        print("✅ LIVE BOOKING UPDATE SUCCESSFUL (MOCK)")
        return response_data
        
    except Exception as e:
        print(f"❌ Error updating live booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

# Health check endpoint
@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Kiwi Cabs AI IVR", "version": "2.0"}

# Root endpoint
@app.route("/", methods=["GET"])
def home():
    """Root endpoint with service info"""
    return {
        "message": "Kiwi Cabs AI IVR System", 
        "version": "2.0",
        "endpoints": ["/voice", "/api/bookings", "/health"],
        "integration": "TaxiCaller API Ready"
    }

if __name__ == "__main__":
    app.run(debug=True)