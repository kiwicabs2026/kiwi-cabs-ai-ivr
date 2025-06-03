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
            # Return TwiML to gather speech with greeting
            twiml = """
<Response>
  <Say voice="Polly.Aria-Neural">
    Kia ora, and welcome to Kiwi Cabs.
    <break time="400ms"/>
    I’m an A.I assistant, here to help you book your taxi.
    <break time="500ms"/>
    This call may be recorded for training and security purposes.
  </Say>
  <Gather input="speech" action="/ask" method="POST">
    <Say voice="Polly.Aria-Neural">
      Please tell me your name, pickup location, destination, and pickup time.
    </Say>
  </Gather>
  <Say>I didn’t hear anything. Goodbye.</Say>
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

        # Replace vague dates
        if "after tomorrow" in prompt.lower():
            day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\bafter tomorrow\\b", day_after, prompt, flags=re.IGNORECASE)
        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btomorrow\\b", tomorrow_date, prompt, flags=re.IGNORECASE)
        if "today" in prompt.lower():
            today_date = datetime.now().strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btoday\\b", today_date, prompt, flags=re.IGNORECASE)

        user_id = request.form.get("From", "default_user")

        # STEP 3: Check if user said yes or no
        if any(word in prompt.lower() for word in ["yes", "yeah", "yep"]):
            parsed = user_sessions.get(user_id)
            if parsed:
                return twiml_response(f"Thanks {parsed.get('name')}, your booking is confirmed. Your reference is your phone number.")
            else:
                return twiml_response("Sorry, I don’t have your previous booking. Please start again.")

        elif any(word in prompt.lower() for word in ["no", "nah", "cancel", "change"]):
            user_sessions.pop(user_id, None)
            return twiml_response("Okay, let's update your booking. Please say your name, pickup location, destination, and pickup time.")

        # STEP 4: Process new booking request via AI
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful A.I assistant for Kiwi Cabs.\n"
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
            print("Parsed JSON:", parsed)
            user_sessions[user_id] = parsed

            confirmation_prompt = (
                f"Hello {parsed.get('name')}, your Kiwi Cab has been scheduled. "
                f"Pick-up: {parsed.get('pickup')}. "
                f"Drop-off: {parsed.get('dropoff')}. "
                f"Time: {parsed.get('time')}. "
                "Say 'yes' to confirm or 'no' to update."
            )
            return twiml_response(confirmation_prompt)

        except json.JSONDecodeError:
            return twiml_response(ai_reply)

    except Exception as e:
        print("ERROR:", str(e))
        return twiml_response("Sorry, an application error occurred.")

def twiml_response(text):
    return f"""
<Response>
  <Say voice="Polly.Aria-Neural">{text}</Say>
</Response>
"""
