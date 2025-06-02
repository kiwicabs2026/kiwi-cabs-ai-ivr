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

@app.route("/ask", methods=["POST"])
def ask():
    try:
        # STEP 1: Handle first call without SpeechResult
        speech_result = request.form.get("SpeechResult")

        if not speech_result:
            # Return TwiML to gather speech
            twiml = """
                <Response>
                    <Gather input="speech" action="/ask" method="POST">
                        <Say voice="Polly.Aria-Neural">Please tell me your name, pickup location, destination, and pickup time.</Say>
                    </Gather>
                    <Say>I didn't hear anything. Goodbye.</Say>
                </Response>
            """
            response = make_response(twiml)
            response.headers["Content-Type"] = "application/xml"
            return response

        # STEP 2: Received actual speech input
        prompt = speech_result.strip()
        print("DEBUG - SpeechResult:", prompt)

        if not prompt:
            return twiml_response("Sorry, I didn’t catch that. Please repeat your booking details.")

        # Replace date references
        if "after tomorrow" in prompt.lower():
            day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\bafter tomorrow\\b", day_after, prompt, flags=re.IGNORECASE)
        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btomorrow\\b", tomorrow_date, prompt, flags=re.IGNORECASE)
        if "today" in prompt.lower():
            today_date = datetime.now().strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btoday\\b", today_date, prompt, flags=re.IGNORECASE)

        # Check for confirmation
        user_id = request.form.get("From", "default_user")

        if prompt.lower() in ["yes", "yeah", "yep", "confirm"]:
            previous = user_sessions.get(user_id)
            if not previous:
                return twiml_response("Sorry, I don’t have your booking details. Please repeat everything.")
            reply = f"Thanks {previous.get('name')}, your booking is confirmed."
            return twiml_response(reply)

        if prompt.lower() in ["no", "nah", "cancel", "change"]:
            user_sessions.pop(user_id, None)
            return twiml_response("Okay, let's start over. Please tell me your name, pickup, drop-off, and time.")

        # Otherwise, assume it's a new booking prompt
        ai_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": (
                    "You are a helpful AI assistant for Kiwi Cabs. When the user provides name, pickup, dropoff and time, confirm like this:\n"
                    "Hello [Name], your Kiwi Cab has been scheduled. Here are the details:\n"
                    "Pick-up: [Pickup]\nDrop-off: [Dropoff]\nTime: [Time]\nSay 'yes' to confirm or 'no' to change."
                )},
                {"role": "user", "content": prompt}
            ]
        )

        raw = ai_response["choices"][0]["message"]["content"]
        print("AI Response:", raw)

        try:
            parsed = json.loads(raw)
            user_sessions[user_id] = parsed
            reply = (
                f"Please confirm your booking. Name: {parsed.get('name')}. "
                f"Pickup: {parsed.get('pickup')}. Drop-off: {parsed.get('dropoff')}. Time: {parsed.get('time')}. "
                "Say 'yes' to confirm or 'no' to change."
            )
        except:
            reply = raw

        return twiml_response(reply)

    except Exception as e:
        print("ERROR:", str(e))
        return twiml_response("Sorry, an error occurred. Please try again.")


def twiml_response(text):
    return f"""
        <Response>
            <Say voice="Polly.Aria-Neural">{text}</Say>
        </Response>
    """, 200, {"Content-Type": "application/xml"}
