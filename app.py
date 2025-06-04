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
            <speak>
                Kia ora, and welcome to Kiwi Cabs.
                <break time='400ms'/>
                I am A I assistant, here to help you book your taxi.
                <break time='400ms'/>
                This call may be recorded for training and security purposes.
                <break time='400ms'/>
                Please listen carefully and respond clearly.
                <break time='300ms'/>
                Say option 1 to book a taxi.
                <break time='300ms'/>
                Say option 2 to change or cancel an existing booking.
                <break time='300ms'/>
                Say option 3 to speak to a team member.
                <break time='400ms'/>
                I am listening.
            </speak>
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/menu", methods=["POST"])
def menu():
    data = request.form.get("SpeechResult", "").lower().strip()
    print("DEBUG - Menu SpeechResult:", data)

    if data in ["1", "option 1", "one", "option one"]:
        return redirect_to("/book")
    elif data in ["2", "option 2", "two", "option two"]:
        return redirect_to("/modify")
    elif data in ["3", "option 3", "three", "option three"]:
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

    # Store booking temporarily
    caller = request.form.get("From", "unknown")
    session = user_sessions.get(caller, {})
    session["latest_booking"] = data
    user_sessions[caller] = session

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
    print("DEBUG - Confirmation Response:", data)

    if "yes" in data:
        caller = request.form.get("From", "unknown")
        booking_data = user_sessions.get(caller, {}).get("latest_booking", "")
        try:
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
    response = """
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Please say the phone number and new time or date you want to change the booking to.</Say>
        <Gather input="speech" action="/ask_modify" method="POST" timeout="10"/>
    </Response>
    """
    return Response(response, mimetype="text/xml")

@app.route("/team", methods=["POST"])
def team():
    return Response("""
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Transferring you to one of our team members now.</Say>
        <Dial>+6441234567</Dial>
    </Response>
    """, mimetype="text/xml")

def redirect_to(path):
    return Response(f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Redirect>{path}</Redirect>
    </Response>
    """, mimetype="text/xml")
