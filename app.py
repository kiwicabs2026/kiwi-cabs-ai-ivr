import os
from flask import Flask, request, jsonify
import openai

app = Flask(__name__)

# Get your OpenAI API key securely via Render environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        # Get JSON data from the incoming POST request
        data = request.get_json()
        print("DEBUG - Incoming data:", data)  # Debug log for Render

        # Combine inputs from all gather widgets (if available)
        prompt = " ".join([
            data.get("widgets", {}).get("gather_trip_details", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_modify_voice", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_cancel_voice", {}).get("SpeechResult", "")
        ]).strip()

        if not prompt:
            return jsonify({"reply": "Sorry, I didn’t catch that. Could you please repeat your booking details?"}), 200

        # Call OpenAI API to simulate AI assistant
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant for Kiwi Cabs. "
                        "You assist callers by taking taxi bookings, modifying booking details, or canceling bookings. "
                        "When the user provides their name, pickup address, destination, and time/date, confirm the booking like this format:\n"
                        "Hello [Name], your Kiwi Cab has been scheduled. Here are the details:\n"
                        "Pick-up: [Pickup Address]\n"
                        "Drop-off: [Dropoff Address]\n"
                        "Time: [Time and Day/Date].\n"
                        "Thank you for choosing Kiwi Cabs.\n"
                        "Do not mention sending notifications or ask if the user needs anything else."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extract the AI's reply
        ai_reply = response["choices"][0]["message"]["content"].strip()
        print("AI RAW REPLY:", ai_reply)
        return jsonify({"reply": ai_reply}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
