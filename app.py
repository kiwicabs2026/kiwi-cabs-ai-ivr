from flask import Flask, request, jsonify
import openai
import json
import os
from datetime import datetime

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_booking_details(speech_text):
    """Robust extraction with fallback values"""
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
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # More deterministic
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        
        # Validation
        required = ["name", "pickup_location", "dropoff_location", "time"]
        return {k: result.get(k, "unknown")[:100] for k in required}  # Truncate long values
        
    except Exception as e:
        print(f"OpenAI Error: {str(e)}")
        return {
            "name": "unknown",
            "pickup_location": "unknown",
            "dropoff_location": "unknown",
            "time": "unknown"
        }

@app.route("/ask", methods=["POST"])
def ask():
    try:
        speech_text = request.form.get("SpeechResult", "")
        print(f"Processing speech: {speech_text}")  # Debug logging
        
        details = extract_booking_details(speech_text)
        
        # Ensure we always return valid TwiML
        return jsonify({
            "actions": [
                {
                    "say": f"""
                    Confirm your booking:
                    Name: {details['name']}
                    From: {details['pickup_location']}
                    To: {details['dropoff_location']}
                    At: {details['time']}
                    Press 1 to confirm or hang up.
                    """
                },
                {
                    "gather": {
                        "numDigits": 1,
                        "action": "/confirm",
                        "method": "POST",
                        "timeout": 10
                    }
                }
            ]
        })
        
    except Exception as e:
        print(f"Critical error: {str(e)}")
        return jsonify({
            "actions": [
                {"say": "System error. Please call back later."},
                {"hangup": True}
            ]
        })

@app.route("/confirm", methods=["POST"])
def confirm():
    if request.form.get("Digits") == "1":
        return jsonify({
            "actions": [
                {"say": "Booking confirmed! Thank you."},
                {"hangup": True}
            ]
        })
    return jsonify({
        "actions": [
            {"say": "Booking cancelled."},
            {"hangup": True}
        ]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
