from flask import Flask, request, jsonify
import openai
import os

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")  # Set your OpenAI key

@app.route("/process_booking", methods=["POST"])
def process_booking():
    speech_text = request.form.get("SpeechResult", "")

    # Step 1: Use OpenAI to extract structured data
    prompt = f"""
    Extract the following from this taxi booking request:
    - name: (e.g., "John Doe")
    - pickup_location: (e.g., "123 Main St")
    - dropoff_location: (e.g., "456 Airport Rd")
    - time: (e.g., "2025-06-20 15:30")

    Return JSON only. Input: "{speech_text}"
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        details = json.loads(response.choices[0].message.content)

        # Step 2: Generate TwiML to play confirmation and gather DTMF
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
                    "timeout": 5,
                    "action": "/confirm_booking",  # Next step
                    "method": "POST"
                }}
            ]
        })

    except Exception as e:
        return jsonify({
            "actions": [
                {"say": "Sorry, I couldn't process your request. Please try again later."},
                {"hangup": True}
            ]
        })

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    if request.form.get("Digits") == "1":
        return jsonify({
            "actions": [
                {"say": "Your booking is confirmed. Thank you!"},
                {"hangup": True}
            ]
        })
    else:
        return jsonify({
            "actions": [
                {"say": "Booking not confirmed. Goodbye!"},
                {"hangup": True}
            ]
        })

if __name__ == "__main__":
    app.run(port=5000)
