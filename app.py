import os
import requests
import json
from flask import Flask, request, Response
from datetime import datetime
import re

app = Flask(__name__)

# Render endpoint configuration
RENDER_ENDPOINT = os.getenv("RENDER_ENDPOINT", "https://your-render-app.onrender.com/api/bookings")
RENDER_API_KEY = os.getenv("RENDER_API_KEY", "")

# Session store for modification bookings (held until confirmed)
# Session memory store for user conversations
user_sessions = {}

# Session store for modification bookings (held until confirmed)
modification_bookings = {}

@app.route("/get_phone_for_booking", methods=["POST"])
def get_phone_for_booking():
    """Get phone number to search for existing booking"""
    phone_speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Phone search: '{phone_speech}' (Confidence: {confidence})")
    
    # Extract phone number from speech
    # Remove common words and extract digits
    import re
    digits_only = re.sub(r'[^\d]', '', phone_speech)
    
    # Common speech-to-text number conversions
    number_words = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'oh': '0'
    }
    
    # Convert spoken numbers to digits
    spoken_phone = phone_speech.lower()
    for word, digit in number_words.items():
        spoken_phone = spoken_phone.replace(word, digit)
    
    # Extract digits from converted speech
    extracted_digits = re.sub(r'[^\d]', '', spoken_phone)
    
    # Use the longer/more complete number
    phone_number = digits_only if len(digits_only) >= len(extracted_digits) else extracted_digits
    
    # Format NZ phone number (remove country code if present)
    if phone_number.startswith('64'):
        phone_number = '0' + phone_number[2:]
    elif len(phone_number) == 9 and not phone_number.startswith('0'):
        phone_number = '0' + phone_number
    
    if len(phone_number) >= 8:  # Valid NZ phone number
        # Store phone for this session
        user_sessions[call_sid] = {'search_phone': phone_number}
        
        # Simulate booking search (in real system, search your booking database)
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Thanks! I found your booking for phone number ending in {phone_number[-4:]}.
        What would you like to change? 
        Say pickup location, destination, or time.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Phone number not clear, ask again
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch your phone number clearly. 
        Please say your phone number again, speaking each digit clearly.
        For example, say zero two one, two three four, five six seven eight.
    </Say>
    <Gather input="speech" action="/get_phone_for_booking" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/voice", methods=["POST"])
def voice():
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/menu" input="speech" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Kia ora, and welcome to Kiwi Cabs.
            I'm your AI assistant, here to help you book your taxi.
            This call may be recorded for training and security purposes.
            Please speak clearly after each prompt.
            Say option one to book a new taxi.
            Say option two to change or cancel an existing booking.
            Say option three to speak with one of our team members.
            What would you like to do today?
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/menu", methods=["POST"])
def menu():
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    print(f"DEBUG - Menu SpeechResult: '{data}' (Confidence: {confidence})")

    # Enhanced NZ English recognition patterns
    booking_keywords = ["1", "one", "book", "taxi", "ride", "cab", "new booking"]
    modify_keywords = ["2", "two", "change", "cancel", "modify", "existing", "alter"]
    team_keywords = ["3", "three", "team", "human", "person", "staff", "operator", "speak"]

    if any(keyword in data for keyword in booking_keywords):
        print("Redirecting to /book")
        return redirect_to("/book")
    elif any(keyword in data for keyword in modify_keywords):
        print("Redirecting to /modify")
        return redirect_to("/modify")
    elif any(keyword in data for keyword in team_keywords):
        print("Redirecting to /team")
        return redirect_to("/team")
    else:
        print("Unrecognized input. Asking for clarification.")
        return clarify_menu()

def clarify_menu():
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
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No problem! I'm connecting you with one of our friendly team members now.
        Please hold the line.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_booking", methods=["POST"])
def process_booking():
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Booking Info: '{data}' (Confidence: {confidence})")
    
    # Store booking info in session
    user_sessions[call_sid] = {
        'booking_details': data,
        'timestamp': request.form.get('Timestamp', '')
    }

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

@app.route("/process_modification", methods=["POST"])
def process_modification():
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Modification Request: '{data}' (Confidence: {confidence})")
    
    # Store the modification request (but don't send to render yet)
    search_phone = user_sessions.get(call_sid, {}).get('search_phone', 'Unknown')
    
    modification_bookings[call_sid] = {
        'phone_number': search_phone,
        'modification_request': data,
        'timestamp': request.form.get('Timestamp', ''),
        'status': 'pending_confirmation'
    }

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Right, I've got your change request: {data}.
        Your booking modification is ready but not yet processed.
        Say yes to confirm and send the changes to our dispatch system, or say no to make different changes.
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

def send_booking_to_render(booking_data):
    """
    Send formatted booking information to TaxiCaller dispatch system via render
    """
    try:
        # Prepare the payload with TaxiCaller format
        taxicaller_payload = {
            'booking_reference': booking_data['booking_reference'],
            'customer_details': {
                'name': booking_data['taxicaller_format']['customer_name'],
                'phone': booking_data['taxicaller_format']['phone_number']
            },
            'trip_details': {
                'pickup_address': booking_data['taxicaller_format']['pickup_address'],
                'destination_address': booking_data['taxicaller_format']['destination_address'],
                'pickup_date': booking_data['taxicaller_format']['booking_date'],
                'pickup_time': booking_data['taxicaller_format']['booking_time']
            },
            'booking_info': {
                'source': 'AI_Phone_System',
                'special_instructions': booking_data['taxicaller_format']['special_instructions'],
                'status': 'confirmed',
                'region': 'Wellington'
            },
            'raw_data': {
                'original_speech': booking_data['raw_speech'],
                'timestamp': booking_data['timestamp']
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-Source': 'KiwiCabs-AI-IVR',
            'Authorization': f'Bearer {RENDER_API_KEY}' if RENDER_API_KEY else None
        }
        
        # Remove None values from headers
        headers = {k: v for k, v in headers.items() if v is not None}
        
        # Log the formatted booking data
        print("=" * 50)
        print("📋 TAXICALLER BOOKING DATA:")
        print(f"👤 Customer: {taxicaller_payload['customer_details']['name']}")
        print(f"📞 Phone: {taxicaller_payload['customer_details']['phone']}")
        print(f"📍 Pickup: {taxicaller_payload['trip_details']['pickup_address']}")
        print(f"🎯 Drop-off: {taxicaller_payload['trip_details']['destination_address']}")
        print(f"📅 Date: {taxicaller_payload['trip_details']['pickup_date']}")
        print(f"⏰ Time: {taxicaller_payload['trip_details']['pickup_time']}")
        print(f"🔢 Reference: {taxicaller_payload['booking_reference']}")
        print("=" * 50)
        
        response = requests.post(
            RENDER_ENDPOINT,
            json=taxicaller_payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Successfully sent booking to TaxiCaller: {booking_data['booking_reference']}")
            print(f"📤 Response: {response.text}")
            return True
        else:
            print(f"❌ Failed to send booking to TaxiCaller. Status: {response.status_code}")
            print(f"📤 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 Error sending booking to TaxiCaller: {str(e)}")
        return False

def parse_booking_details(speech_text, caller_number):
    """
    Parse booking details and format for TaxiCaller dispatch system
    Required format: name + NZ Wellington addresses + date/time (DD/MM/YYYY HH:MM AM/PM) + phone
    """
    from datetime import datetime
    import re
    
    # Clean phone number format
    clean_phone = caller_number.replace('+64', '0').replace(' ', '').replace('-', '')
    
    booking_data = {
        'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'caller_number': clean_phone,
        'raw_speech': speech_text,
        'timestamp': datetime.now().isoformat(),
        'status': 'confirmed',
        'taxicaller_format': {}  # This will contain the formatted data for dispatch
    }
    
    text_lower = speech_text.lower()
    
    # Extract customer name with enhanced patterns
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
            # Filter out common location words
            if not any(word in name_candidate for word in ['street', 'road', 'avenue', 'drive', 'wellington', 'airport']):
                customer_name = name_candidate.title()
                break
    
    # Wellington-specific location patterns and common addresses
    wellington_locations = {
        # CBD and Central Wellington
        'queen street': 'Queen Street, Wellington Central, Wellington',
        'cuba street': 'Cuba Street, Wellington Central, Wellington', 
        'lambton quay': 'Lambton Quay, Wellington Central, Wellington',
        'willis street': 'Willis Street, Wellington Central, Wellington',
        'courtenay place': 'Courtenay Place, Wellington Central, Wellington',
        'manners street': 'Manners Street, Wellington Central, Wellington',
        'the terrace': 'The Terrace, Wellington Central, Wellington',
        'featherston street': 'Featherston Street, Wellington Central, Wellington',
        
        # Transport Hubs
        'wellington airport': 'Wellington Airport, Rongotai, Wellington',
        'airport': 'Wellington Airport, Rongotai, Wellington',
        'wellington station': 'Wellington Railway Station, Pipitea, Wellington',
        'train station': 'Wellington Railway Station, Pipitea, Wellington',
        'railway station': 'Wellington Railway Station, Pipitea, Wellington',
        'interislander': 'Interislander Terminal, Aotea Quay, Wellington',
        'ferry terminal': 'Interislander Terminal, Aotea Quay, Wellington',
        
        # Suburbs
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
        """Find and format Wellington addresses"""
        for location_key, full_address in wellington_locations.items():
            if location_key in text_segment:
                return full_address
        
        # If no exact match, try to extract street names
        street_patterns = [
            r'([a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way))',
            r'([a-zA-Z\s]+(?:st|rd|ave|dr|pl|tce|cres))'
        ]
        
        for pattern in street_patterns:
            match = re.search(pattern, text_segment)
            if match:
                street_name = match.group(1).strip().title()
                return f"{street_name}, Wellington"
        
        # Default fallback
        return text_segment.strip().title() + ", Wellington"
    
    # Extract pickup location
    pickup_patterns = [
        r'(?:from|pickup|pick up|starting from|at)\s+([^,]+?)(?:\s+(?:to|going|destination|and then))',
        r'(?:from|pickup|pick up|at)\s+([^,]+?)(?:\s+and|\s+then|\s+at\s+\d)',
    ]
    
    pickup_location = "Wellington Central, Wellington"  # Default
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
    
    destination = "Wellington Central, Wellington"  # Default
    for pattern in destination_patterns:
        match = re.search(pattern, text_lower)
        if match:
            dest_text = match.group(1).strip()
            destination = find_wellington_address(dest_text)
            break
    
    # Parse time and create NZ formatted date/time
    current_time = datetime.now()
    requested_datetime = current_time  # Default to now
    
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
            
            # Convert to 24-hour format
            if am_pm:
                if am_pm.lower() == 'pm' and hour != 12:
                    hour += 12
                elif am_pm.lower() == 'am' and hour == 12:
                    hour = 0
            
            # Create the datetime for today at the specified time
            try:
                requested_datetime = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                # If the time has already passed today, schedule for tomorrow
                if requested_datetime < current_time:
                    from datetime import timedelta
                    requested_datetime += timedelta(days=1)
            except ValueError:
                # Invalid time, use current time
                requested_datetime = current_time
            break
    
    # Handle special time keywords
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
    
    # Format date and time for TaxiCaller (NZ format: DD/MM/YYYY HH:MM AM/PM)
    formatted_date = requested_datetime.strftime('%d/%m/%Y')
    formatted_time = requested_datetime.strftime('%I:%M %p')
    
    # Create TaxiCaller formatted booking data
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
    
    # Also keep parsed details for internal use
    booking_data['parsed_details'] = {
        'name': customer_name,
        'pickup_location': pickup_location,
        'destination': destination,
        'requested_datetime': requested_datetime.isoformat(),
        'phone': clean_phone
    }
    
    return booking_data

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"DEBUG - Booking Confirmation: '{data}' (Confidence: {confidence})")

    # NZ English confirmation patterns
    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        # Get booking details from session
        booking_details = user_sessions.get(call_sid, {}).get('booking_details', '')
        
        # Parse and prepare booking data with TaxiCaller formatting
        booking_data = parse_booking_details(booking_details, caller_number)
        
        # Log the complete booking for debugging
        print("🚕 COMPLETE BOOKING DATA FOR TAXICALLER:")
        print(json.dumps(booking_data['taxicaller_format'], indent=2))
        
        # Send booking information to TaxiCaller via render
        render_success = send_booking_to_render(booking_data)
        
        # Simple confirmation message
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
        # Unclear response, ask again
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/confirm_modification", methods=["POST"])
def confirm_modification():
    data = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    print(f"DEBUG - Modification Confirmation: '{data}'")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "good", "sweet", "confirm"]
    no_patterns = ["no", "nah", "wrong", "different", "change"]
    
    if any(pattern in data for pattern in yes_patterns):
        # Get the held modification booking
        modification_data = modification_bookings.get(call_sid, {})
        
        if modification_data:
            # NOW send to render/dispatch system
            try:
                modification_payload = {
                    'action': 'modify_booking',
                    'phone_number': modification_data['phone_number'],
                    'modification_request': modification_data['modification_request'],
                    'timestamp': modification_data['timestamp'],
                    'status': 'confirmed'
                }
                
                # Send to render endpoint
                headers = {
                    'Content-Type': 'application/json',
                    'X-API-Source': 'KiwiCabs-AI-IVR-Modification'
                }
                
                print("🔄 SENDING BOOKING MODIFICATION TO DISPATCH:")
                print(f"📞 Phone: {modification_data['phone_number']}")
                print(f"✏️  Changes: {modification_data['modification_request']}")
                
                response = requests.post(
                    RENDER_ENDPOINT,
                    json=modification_payload,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    print("✅ Modification sent successfully")
                    # Clean up the held booking
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
                    print(f"❌ Failed to send modification: {response.status_code}")
                    
            except Exception as e:
                print(f"💥 Error sending modification: {str(e)}")
        
        # Fallback response if sending fails
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Your booking modification has been noted. 
        Our team will process the changes and call you back shortly to confirm.
        Thanks for using Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        
    elif any(pattern in data for pattern in no_patterns):
        # Go back to ask what they want to change
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! What would you like to change about your booking?
        Say pickup location, destination, or time.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    else:
        # Unclear response
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that. Please say yes to confirm your booking changes, or no to make different changes.
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

def redirect_to(path):
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

# API endpoint to receive booking data (for testing)
@app.route("/api/bookings", methods=["POST"])
def receive_booking():
    """
    Test endpoint to receive booking data
    """
    try:
        booking_data = request.get_json()
        print(f"Received booking data: {json.dumps(booking_data, indent=2)}")
        return {"status": "success", "message": "Booking received", "booking_id": booking_data.get('booking_reference')}
    except Exception as e:
        print(f"Error receiving booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

# Health check endpoint
@app.route("/health", methods=["GET"])
def health():
    return {"status": "healthy", "service": "Kiwi Cabs AI IVR"}

# Root endpoint
@app.route("/", methods=["GET"])
def home():
    return {"message": "Kiwi Cabs AI IVR System", "status": "running", "endpoints": ["/voice", "/health", "/api/bookings"]}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)