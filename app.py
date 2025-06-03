from flask import Flask, request, make_response
import openai
import os
import json
from datetime import datetime, timedelta
import re
import requests

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Memory store for session context
user_sessions = {}

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_id = request.form.get("From", "default_user")
        speech_result = request.form.get("SpeechResult", "").strip()
        print("DEBUG - SpeechResult:", speech_result)

        # Step 1: First call with no speech input
        if not speech_result:
            greeting = """
            <Response>
                <Say voice="Polly.Aria-Neural">
                    Kia ora, and welcome to Kiwi Cabs. I’m an A.I. assistant and I understand what you say.
                    <break time="300ms"/>
                    Please tell me your name, pickup location, destination, and pickup time.
                </Say>
            </Response>
            """
            response = make_response(greeting)
            response.headers["Content-Type"] = "application/xml"
            return response

        # Step 2: Replace vague time expressions
        prompt = speech_result
        if "after tomorrow" in prompt.lower():
            day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\bafter tomorrow\\b", day_after, prompt, flags=re.IGNORECASE)
        if "tomorrow" in prompt.lower():
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btomorrow\\b", tomorrow, prompt, flags=re.IGNORECASE)
        if "today" in prompt.lower():
            today = datetime.now().strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btoday\\b", today, prompt, flags=re.IGNORECASE)

        # Step 3: Handle yes/no response
        if prompt.lower() in ["yes", "yeah", "confirm", "go ahead"]:
            parsed = user_sessions.get(user_id)
            if parsed:
                # Send to TaxiCaller (pseudo-code)
                job_data = {
                    "apiKey": os.getenv("TAXICALLER_API_KEY"),
                    "name": parsed.get("name"),
                    "pickup": parsed.get("pickup"),
                    "dropoff": parsed.get("dropoff"),
                    "time": parsed.get("time")
                }
                print("DEBUG - Sending job to TaxiCaller:", job_data)
                # You would make actual requests.post() to TaxiCaller here
                return twiml_response("Thanks, your booking is confirmed and has been dispatched.")
            else:
                return twiml_response("Sorry, I don't have your booking info. Please say your booking details again.")

        elif prompt.lower() in ["no", "nah", "cancel", "change", "not correct"]:
            user_sessions.pop(user_id, None)
            return twiml_response("No problem. Please say your name, pickup, drop-off, and pickup time again.")

        # Step 4: Handle booking request
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI taxi assistant for Kiwi Cabs in Wellington.\n"
                        "When the user gives you their name, pickup, drop-off, and time, reply like:\n"
                        "Hello [name], your Kiwi Cab has been scheduled. Pick-up: [pickup]. Drop-off: [dropoff]. Time: [time].\n"
                        "Then say: Say 'yes' to confirm or 'no' to change."
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
            confirmation = (
                f"Hello {parsed.get('name')}, your Kiwi Cab has been scheduled. "
                f"Pick-up: {parsed.get('pickup')}. "
                f"Drop-off: {parsed.get('dropoff')}. "
                f"Time: {parsed.get('time')}. Say 'yes' to confirm or 'no' to change."
            )
            return twiml_response(confirmation)
        except json.JSONDecodeError:
            return twiml_response(ai_reply)

    except Exception as e:
        print("ERROR:", str(e))
        return twiml_response("Sorry, an error occurred. Please try again.")

def twiml_response(text):
    return f"""
    <Response>
        <Say voice="Polly.Aria-Neural">{text}</Say>
    </Response>
    """
