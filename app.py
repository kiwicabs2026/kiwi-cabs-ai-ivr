from flask import Flask, request, jsonify
import openai
import json
import os
from datetime import datetime

app = Flask(__name__)

# Configure OpenAI (set your API key in environment variables)
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_booking_details(speech_text):
    """Use OpenAI to extract structured booking details from speech."""
    prompt = f"""
    Extract the following from the taxi booking request:
    - name: (e.g., "John Doe")
    - pickup_location: (e.g., "123 Main St")
    - dropoff_location: (e.g., "456 Airport Rd")
    - time: (e.g., "tomorrow at 8 PM")

    Return JSON only. Input: "{speech_text}"

    Example Output:
    {{
      "name": "Raj",
      "pickup_location": "Mohali",
      "dropoff_location": "Chandigarh",
      "time": "tomorrow at 8 PM"
    }}
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return None

@app.route("/ask", methods=["POST"])
def ask():
    """Twilio Studio webhook endpoint (replaces your current /ask)"""
    speech_text = request.form.get("SpeechResult", "")
    
    # Handle empty input
    if not speech_text.strip():
        return jsonify({
            "actions": [
                {"say": "I didn't hear you. Please say your name, pickup, drop-off, and time."},
                {"listen": True}  # Re-prompt for speech
            ]
        })

    # Extract details using OpenAI
    details = extract_booking_details(speech_text)
    if not details:
        return jsonify({
            "actions": [
                {"say": "Sorry, I couldn't understand your request. Let's try again."},
                {"redirect": "task://gather_trip_details"}  # Loop back to speech input
            ]
        })

    # Generate confirmation message
    confirm_msg = (
        f"Please confirm your booking. "
        f"Name: {details.get('name', 'N/A')}. "
        f"Pickup: {details.get('pickup_location', 'N/A')}. "
        f"Dropoff: {details.get('dropoff_location', 'N/A')}. "
        f"Time: {details.get('time', 'N/A')}. "
        "Press 1 to confirm, or hang up to cancel."
    )

    return jsonify({
        "actions": [
            {"say": confirm_msg},
            {"gather": {
                "numDigits": 1,
                "timeout": 10,
                "action": "/confirm_booking",
                "method": "POST"
            }}
        ]
    })

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Handle booking confirmation (DTMF 1)."""
    if request.form.get("Digits") == "1":
        return jsonify({
            "actions": [
                {"say": "Your taxi is booked! Thank you for choosing us."},
                {"hangup": True}
            ]
        })
    else:
        return jsonify({
            "actions": [
                {"say": "Booking cancelled. Goodbye!"},
                {"hangup": True}
            ]
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
