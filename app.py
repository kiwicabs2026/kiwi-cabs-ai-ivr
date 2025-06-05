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

# Session memory store for user conversations
user_sessions = {}

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
        Please tell me your name and what you'd like to change about your booking.
        Is it the time, pickup location, or destination?
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="10" language="en-NZ" speechTimeout="2" finishOnKey=""/>
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
        Thanks for that information. Let me confirm your booking details.
        You said: {data}.
        Is this correct? Say yes to confirm your booking, or say no if you need to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_modification", methods=["POST"])
def process_modification():
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    
    print(f"DEBUG - Modification Request: '{data}' (Confidence: {confidence})")

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Right, I've got your modification request: {data}.
        Say yes if this is correct and I'll process the change, or say no to try again.
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

def send_booking_to_render(booking_data):
    """
    Send booking information to render endpoint
    """
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {RENDER_API_KEY}' if RENDER_API_KEY else None
        }
        
        # Remove None values from headers
        headers = {k: v for k, v in headers.items() if v is not None}
        
        response = requests.post(
            RENDER_ENDPOINT,
            json=booking_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"Successfully sent booking to render: {booking_data['booking_reference']}")
            return True
        else:
            print(f"Failed to send booking to render. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error sending booking to render: {str(e)}")
        return False

def parse_booking_details(speech_text, caller_number):
    """
    Parse booking details from speech text using basic patterns
    """
    booking_data = {
        'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'caller_number': caller_number,
        'raw_speech': speech_text,
        'timestamp': datetime.now().isoformat(),
        'status': 'confirmed',
        'parsed_details': {}
    }
    
    # Basic parsing - you can enhance this with more sophisticated NLP
    text_lower = speech_text.lower()
    
    # Try to extract name (usually comes first)
    name_patterns = [
        r'my name is ([a-zA-Z\s]+)',
        r'i\'m ([a-zA-Z\s]+)',
        r'this is ([a-zA-Z\s]+)',
        r'^([a-zA-Z\s]+)(?:\s+from|\s+at|\s+pickup)'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text_lower)
        if match:
            booking_data['parsed_details']['name'] = match.group(1).strip().title()
            break
    
    # Try to extract pickup location
    pickup_patterns = [
        r'(?:from|pickup|pick up|at|starting from)\s+([^,]+?)(?:\s+(?:to|going|destination))',
        r'(?:from|pickup|pick up|at)\s+([^,]+?)(?:\s+and|\s+then|\s+at\s+\d)',
    ]
    
    for pattern in pickup_patterns:
        match = re.search(pattern, text_lower)
        if match:
            booking_data['parsed_details']['pickup_location'] = match.group(1).strip().title()
            break
    
    # Try to extract destination
    destination_patterns = [
        r'(?:to|going to|destination)\s+([^,]+?)(?:\s+(?:at|for|by)|\s+\d|$)',
        r'(?:to|going to|destination)\s+([^,]+?)(?:\s+and|\s+then)',
    ]
    
    for pattern in destination_patterns:
        match = re.search(pattern, text_lower)
        if match:
            booking_data['parsed_details']['destination'] = match.group(1).strip().title()
            break
    
    # Try to extract time
    time_patterns = [
        r'(?:at|for|by)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|o\'clock)?)',
        r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|o\'clock))',
        r'(?:at|for|by)\s+(morning|afternoon|evening|night)',
        r'(now|asap|as soon as possible|immediately)'
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            booking_data['parsed_details']['requested_time'] = match.group(1).strip()
            break
    
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
        
        # Parse and prepare booking data
        booking_data = parse_booking_details(booking_details, caller_number)
        
        # Send booking information to render endpoint
        render_success = send_booking_to_render(booking_data)
        
        if render_success:
            success_message = f"""Excellent! Your taxi has been successfully booked.
            Your booking reference is {booking_data['booking_reference']}.
            The booking details have been sent to our dispatch system.
            Thanks for choosing Kiwi Cabs. Have a great day!"""
        else:
            success_message = f"""Your taxi booking has been confirmed.
            Your booking reference is {booking_data['booking_reference']}.
            Our team will contact you shortly to confirm the details.
            Thanks for choosing Kiwi Cabs!"""
        
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
    print(f"DEBUG - Modification Confirmation: '{data}'")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "good", "sweet"]
    
    if any(pattern in data for pattern in yes_patterns):
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! I've processed your booking changes.
        You'll get a text confirmation with the updated details.
        Thanks for using Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    else:
        return redirect_to("/modify")

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