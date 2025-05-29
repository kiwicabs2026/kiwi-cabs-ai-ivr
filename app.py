import os
from flask import Flask, request, jsonify
import openai

app = Flask(__name__)

# Load API key from environment variable in Render
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        # Get the full JSON payload from Twilio
        data = request.get_json()
        print("DEBUG - Incoming data:", data)

        # Combine text from available widgets (if any)
        prompt = " ".join([
            data.get("widgets", {}).get("gather_trip_details", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_modify_voice", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_cancel_voice", {}).get("SpeechResult", "")
        ]).strip()

        if not prompt:
            return jsonify({"reply": "Sorry, I didn’t catch that. Could you please repeat your booking details?"}), 200

        # Build messages for OpenAI
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant for Kiwi Cabs.\n"
                    "You help users book taxis, modify details, or cancel bookings.\n"
                    "When the user provides a name, pickup address, drop-off address, and time/date, "
                    "respond clearly confirming the job. Speak like a real assistant."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        # Call OpenAI ChatCompletion
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages
        )

        ai_reply = response["choices"][0]["message"]["content"].strip()
        print("AI RAW REPLY:", ai_reply)

        return jsonify({"reply": ai_reply}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
