import os
import json
from flask import Flask, request, Response, jsonify
import openai
from datetime import datetime

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

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
                I’m listening.
            </speak>
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/menu", methods=["POST"])
def menu():
    data = request.form.get("SpeechResult", "").lower()
    print("DEBUG - Menu SpeechResult:", data)

    if "1" in data or "one" in data or "option 1" in data:
        return redirect_to("/book")
    elif "2" in data or "two" in data or "option 2" in data:
        return redirect_to("/modify")
    elif "3" in data or "three" in data or "option 3" in data:
        return redirect_to("/team")
    else:
        return redirect_to("/voice")

@app.route("/book", methods=["POST"])
def book():
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/ask" method="POST" timeout="10">
        <Say>
            Please tell me your name, pickup location, destination, and time.
        </Say>
    </Gather>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.form.get("SpeechResult", "")
    print("DEBUG - Booking Info Captured:", data)

    # You can send data to Render or external API here if needed

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/confirm" method="POST" timeout="5">
        <Say>
            Let me confirm your booking. {data}. Say yes to confirm or no to change.
        </Say>
    </Gather>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/confirm", methods=["POST"])
def confirm():
    data = request.form.get("SpeechResult", "").lower()
    print("DEBUG - Confirmation Response:", data)

    if "yes" in data:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Thanks. Your taxi has been booked. Thank you for using Kiwi Cabs.</Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    else:
        return redirect_to("/book")

def redirect_to(path):
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")
