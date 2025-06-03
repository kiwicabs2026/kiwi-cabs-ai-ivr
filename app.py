from flask import Flask, request, make_response
import openai
import os
import json
from datetime import datetime, timedelta
import re

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Memory store
user_sessions = {}

def twiml_response(text):
    return f"""
    <Response>
        <Say voice="Polly.Aria-Neural">{text}</Say>
    </Response>
    """

def twiml_greeting():
    return """
    <Response>
        <Say voice="Polly.Aria-Neural">
            Kia ora, and welcome to Kiwi Cabs. 
            I’m an A.I. assistant – a smart voice agent that understands what you say.
            I'm here to help you book your taxi easily.
            This call may be recorded for training and security purposes.
        </Say>
        <Pause length="1"/>
        <Redirect method="POST">/ask</Redirect>
    </Response>
    """

@app.route("/ask", methods=["POST"])
def ask():
    try:
        speech_result = request.form.get("SpeechResult")
        user_id = request.form.get("From", "default_user")

        # If it's the first call without speech input
        if not speech_result:
            return make_response(twiml_greeting(), 200, {"Content-Type": "application/xml"})

        prompt = speech_result.strip()
        print("DEBUG - SpeechResult:", prompt)

        if not prompt:
            return make_response(twiml_response("Sorry, I didn’t catch that. Please repeat your booking details."), 200, {"Content-Type": "application/xml"})

        # Normalize vague date references
        if "after tomorrow" in prompt.lower():
            day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\bafter tomorrow\\b", day_after, prompt, flags=re.IGNORECASE)
        if "tomorrow" in prompt.lower():
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btomorrow\\b", tomorrow, prompt, flags=re.IGNORECASE)
        if "today" in prompt.lower():
            today = datetime.now().strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btoday\\b", today, prompt, flags=re.IGNORECASE)

        # If caller confirms
        if any(word in prompt.lower() for word in ["yes", "yeah", "yep"]):
            parsed = user_sessions.get(user_id)
            if parsed:
                return make_response(twiml_response(f"Thanks {parsed.get('name')}, your booking is confirmed. Your reference is your phone number."), 200, {"Content-Type": "application/xml"})
            else:
                return make_response(twiml_response("Sorry, I don’t have your previous booking. Please start again."), 200, {"Content-Type": "application/xml"})

        # If caller rejects and wants to update
        elif any(word in prompt.lower() for word in ["no", "nah", "cancel", "change"]):
            user_sessions.pop(user_id, None)
            return make_response(twiml_response("Okay, let's update your booking. Please say your name, pickup location, destination, and pickup time."), 200, {"Content-Type": "application/xml"})

        # AI to process new booking
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant for Kiwi Cabs.\n"
                        "You assist with taxi bookings. When the user provides name, pickup, drop-off, and time/date, confirm like this:\n"
                        "Hello [Name], your Kiwi Cab has been scheduled. Pick-up: [Pickup]. Drop-off: [Dropoff]. Time: [Time].\n"
                        "Ask: Say 'yes' to confirm or 'no' to update."
                    )
                },
                {"role": "user", "content": prompt}
            ]
        )

        ai_reply = response["choices"][0]["message"]["content"].strip()
        print("AI RAW REPLY:", ai_reply)

        try:
            parsed = json.loads(ai_reply)
            user_sessions[user_id] = parsed
            confirmation_text = (
                f"Hello {parsed.get('name')}, your Kiwi Cab has been scheduled. "
                f"Pick-up: {parsed.get('pickup')}. Drop-off: {parsed.get('dropoff')}. Time: {parsed.get('time')}. "
                "Say 'yes' to confirm or 'no' to update."
            )
            return make_response(twiml_response(confirmation_text), 200, {"Content-Type": "application/xml"})

        except json.JSONDecodeError:
            return make_response(twiml_response(ai_reply), 200, {"Content-Type": "application/xml"})

    except Exception as e:
        print("ERROR:", str(e))
        return make_response(twiml_response("Sorry, an application error occurred."), 200, {"Content-Type": "application/xml"})
