import os
import json
import re
from datetime import datetime, timedelta
from flask import Flask, request, make_response
import openai

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Session memory store
user_sessions = {}

@app.route("/ask", methods=["POST"])
def ask():
    try:
        # STEP 1: Handle first call without SpeechResult
        speech_result = request.form.get("SpeechResult")

        if not speech_result:
            twiml = """
<Response>
  <Gather input="speech" action="/ask" method="POST">
    <Say voice="Polly.Aria-Neural" language="en-NZ">
      Kia ora, and welcome to Kiwi Cabs.
      I’m an A. I. assistant, here to help you book your taxi.
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
            twiml = """
<Response>
  <Say voice="Polly.Aria-Neural" language="en-NZ">
    Sorry, I didn’t catch that. Please repeat your booking details.
  </Say>
</Response>
"""
            return make_response(twiml, 200, {"Content-Type": "application/xml"})

        # Replace vague date terms
        if "after tomorrow" in prompt.lower():
            day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\bafter tomorrow\\b", day_after, prompt, flags=re.IGNORECASE)

        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btomorrow\\b", tomorrow_date, prompt, flags=re.IGNORECASE)

        if "today" in prompt.lower():
            today_date = datetime.now().strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btoday\\b", today_date, prompt, flags=re.IGNORECASE)

        print("DEBUG - Final Prompt:", prompt)

        # Call OpenAI to get AI response
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": (
                    "You are a helpful AI assistant for Kiwi Cabs.\n"
                    "You assist with taxi bookings.\n"
                    "When the user provides all info (name, pickup, dropoff, time), respond in this exact format:\n"
                    "Hello [Name], your Kiwi Cab has been scheduled.\n"
                    "Pick-up: [Pickup]\nDrop-off: [Dropoff]\nTime: [Time]\n"
                    "Please say 'yes' to confirm or 'no' to update."
                )},
                {"role": "user", "content": prompt}
            ]
        )

        ai_reply = response["choices"][0]["message"]["content"].strip()
        print("AI REPLY:", ai_reply)

        # Save session
        user_id = request.form.get("CallSid", "default_user")
        user_sessions[user_id] = ai_reply

        # Respond with AI reply using Polly voice
        twiml = f"""
<Response>
  <Say voice="Polly.Aria-Neural" language="en-NZ">{ai_reply}</Say>
</Response>
"""
        return make_response(twiml, 200, {"Content-Type": "application/xml"})

    except Exception as e:
        print("ERROR:", str(e))
        twiml = f"""
<Response>
  <Say voice="Polly.Aria-Neural" language="en-NZ">
    We’re sorry, an application error has occurred. Please try again later.
  </Say>
</Response>
"""
        return make_response(twiml, 200, {"Content-Type": "application/xml"})
