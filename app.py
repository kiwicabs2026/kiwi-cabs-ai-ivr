import os
from flask import Flask, request, jsonify
import openai
from datetime import datetime, timedelta

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        # Get JSON data from the request
        data = request.get_json()
        print("DEBUG - Incoming data:", data)

        # Gather input from all widgets
        prompt = " ".join([
            data.get("widgets", {}).get("gather_trip_details", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_modify_voice", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_cancel_voice", {}).get("SpeechResult", "")
        ]).strip()

        # Replace "tomorrow" with NZ-style date (DD/MM/YYYY)
        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            words = prompt.split()
            prompt = " ".join(
                [tomorrow_date if word.lower() == "tomorrow" else word for word in words]
            )

        if not prompt:
            return jsonify({"reply": "Sorry, I didn’t catch that. Could you please repeat your booking details?"}), 200

        # OpenAI system instruction
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant for Kiwi Cabs.\n"
                        "You assist callers by taking taxi bookings, modifying details, or canceling bookings.\n"
                        "When the user provides name, pickup address, destination, and time/date, confirm like this:\n"
                        "Hello [Name], your Kiwi Cab has been scheduled. Here are the details:\n"
                        "Pick-up: [Pickup Address]\n"
                        "Drop-off: [Dropoff Address]\n"
                        "Time: [Time and Date]\n"
                        "Thank you for choosing Kiwi Cabs.\n"
                        "Do not say anything about notifications or further help."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        ai_reply = response["choices"][0]["message"]["content"].strip()
        print("AI RAW REPLY:", ai_reply)
        return jsonify({"reply": ai_reply}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
