import os
import json
from flask import Flask, request, Response, jsonify
import openai
from datetime import datetime
import re

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Session memory store
user_sessions = {}

@app.route("/voice", methods=["POST"])
def voice():
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/menu" input="speech" method="POST" timeout="5">
        <Say language="en-NZ">
            Kia ora, and welcome to Kiwi Cabs. I am A I assistant, here to help you book your taxi. 
            This call may be recorded for training and security purposes. 
            Please listen carefully and respond clearly. 
            Say option 1 to book a taxi. 
            Say option 2 to change or cancel an existing booking. 
            Say option 3 to speak to a team member. 
            I am listening.
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/menu", methods=["POST"])
def menu():
    data = request.form.get("SpeechResult", "").lower()
    print("DEBUG - Menu SpeechResult:", data)

    if "1" in data or "one" in data:
        return redirect_to("/book")
    elif "2" in data or "two" in data:
        return redirect_to("/modify")
    elif "3" in data or "three" in data:
        return redirect_to("/team")
    else:
        return redirect_to("/voice")

@app.route("/book", methods=["POST"])
def book():
    response = """
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>I’m listening. Please tell me your name, pickup location, destination, and time.</Say>
        <Gather input="speech" action="/ask" method="POST" timeout="10"/>
    </Response>
    """
    return Response(response, mimetype="text/xml")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.form.get("SpeechResult", "")
    print("DEBUG - Booking Info Captured:", data)

    caller = request.form.get("From", "unknown")
    user_sessions[caller] = {"latest_booking": data}

    response = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Let me confirm your booking. {data}. Say yes to confirm or no to change.</Say>
        <Gather input="speech" action="/confirm" method="POST" timeout="5"/>
    </Response>
    """
    return Response(response, mimetype="text/xml")

@app.route("/confirm", methods=["POST"])
def confirm():
    data = request.form.get("SpeechResult", "").lower()
    caller = request.form.get("From", "unknown")
    print("DEBUG - Confirmation Response:", data)

    if "yes" in data:
        booking_data = user_sessions.get(caller, {}).get("latest_booking", "")
        try:
            import requests
            requests.post("https://your-render-url.com/bookings", json={"details": booking_data})
        except Exception as e:
            print("Failed to send to Render:", e)

        return Response("""
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say>Thanks. Your taxi has been booked. Thank you for using Kiwi Cabs.</Say>
            <Hangup/>
        </Response>
        """, mimetype="text/xml")
    else:
        return redirect_to("/book")

@app.route("/modify", methods=["POST"])
def modify():
    return Response("""
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Please say the phone number and new time or date you want to change the booking to.</Say>
        <Gather input="speech" action="/ask_modify" method="POST" timeout="10"/>
    </Response>
    """, mimetype="text/xml")

@app.route("/team", methods=["POST"])
def team():
    return Response("""
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Please wait while we connect you to a team member.</Say>
        <Dial>+648966156</Dial>
    </Response>
    """, mimetype="text/xml")

def redirect_to(path):
    return Response(f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Redirect>{path}</Redirect>
    </Response>
    """, mimetype="text/xml")
