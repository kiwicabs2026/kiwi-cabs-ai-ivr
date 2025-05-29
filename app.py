import os
from flask import Flask, request, jsonify
import openai
from datetime import datetime, timedelta

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        print("DEBUG - Incoming data:", data)

        # Safe default empty string for each widget
        if not isinstance(data.get("widgets"), dict):
            return jsonify({"reply": "Invalid request format — 'widgets' must be an object."}), 400

        trip = data["widgets"].get("gather_trip_details", {}).get("SpeechResult", "")
        modify = data["widgets"].get("gather_modify_voice", {}).get("SpeechResult", "")
        cancel = data["widgets"].get("gather_cancel_voice", {}).get("SpeechResult", "")

        prompt = " ".join([trip, modify, cancel]).strip()

        # Replace 'tomorrow' with NZ-style date
        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            words = prompt.split()
            prompt = " ".join([tomorrow_date if word.lower() == "tomorrow" else word for word in words])

        if not prompt:
            return jsonify({"reply": "Sorry, I didn’t catch that. Could you please repeat your booking details?"}), 200

        # Call OpenAI with booking assistant instructions
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant for Kiwi Cabs. "
                        "You can assist callers by taking taxi bookings, modifying details, or canceling bookings. "
                        "When the user provides name, pickup address, destination, and time/date, respond clearly like this:\n"
                        "Hello [Name], your Kiwi Cab has been scheduled. Here are the details:\n"
                        "Pick-up: [Pickup Address]\n"
                        "Drop-off: [Dropoff Address]\n"
                        "Time: [Time and Date]\n"
                        "Thank you for choosing Kiwi Cabs.\n"
                        "Do not say anything about notifications or ask if they need anything else."
                    )
                },
                {"role": "user", "content": prompt}
            ]
        )

        ai_reply = response["choices"][0]["message"]["content"].strip()
        print("AI RAW REPLY:", ai_reply)
        return jsonify({"reply": ai_reply}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
