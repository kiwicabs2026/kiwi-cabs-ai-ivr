from flask import Flask, request, Response
import openai
import json
import os
from datetime import datetime
from twilio.twiml.voice_response import VoiceResponse, Gather

app = Flask(__name__)

# Load OpenAI key from env
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_booking_details(speech_text):
    """Extracts structured booking info from speech using OpenAI"""
    prompt = f"""
    Extract exactly these fields from the taxi request:
    - name (string): "unknown" if not provided
    - pickup_location (string): Must contain at least a landmark
    - dropoff_location (string): Must contain at least a landmark
    - time (string): In natural language like "today 3 PM"

    Input: "{speech_text}"

    Return JSON with ALL these fields. Example:
    {{
      "name": "Raj",
      "pickup_location": "Gate 3, Mohali",
      "dropoff_location": "Sector 17, Chandigarh",
      "time": "tomorrow at 8 PM"
    }}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or "gpt-4o" if available
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )

        result = json.loads(response.choices[0].message.content)

        # Ensure all required fields are returned
        required = ["name", "pickup_location", "dropoff_location", "time"]
        return {k: str(result.get(k, "unknown"))[:100] for k in required}

    except Exception as e:
        print(f"[OpenAI ERROR] {str(e)}")
        return {
            "name": "unknown",
            "pickup_location": "unknown",
            "dropoff_location": "unknown",
            "time": "unknown"
        }

@app.route("/ask", methods=["POST"])
def ask():
    speech_text = request.form.get("SpeechResult", "")
    print(f"[Speech Input] {speech_text}")

    details = extract_booking_details(speech_text)
    print(f"[Extracted Details] {json.dumps(details, indent=2)}")

    response = VoiceResponse()

    # Gather DTMF input for confirmation
    gather = Gather(num_digits=1, action="/confirm", method="POST", timeout=10)
    gather.say(
        f"Please confirm your booking. "
        f"Name: {details['name']}. "
        f"From: {details['pickup_location']}. "
        f"To: {details['dropoff_location']}. "
        f"At: {details['time']}. "
        f"Press 1 to confirm or hang up to cancel.",
        voice='alice',
        language='en-IN'
    )
    response.append(gather)

    # Fallback if no input received
    response.say("We did not receive your input. Please try again later.", voice='alice')
    response.hangup()

    return Response(str(response), mimetype='application/xml')

@app.route("/confirm", methods=["POST"])
def confirm():
    digit = request.form.get("Digits")
    response = VoiceResponse()

    if digit == "1":
        response.say("Booking confirmed! Thank you.", voice='alice')
    else:
        response.say("Booking cancelled.", voice='alice')

    response.hangup()
    return Response(str(response), mimetype='application/xml')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
