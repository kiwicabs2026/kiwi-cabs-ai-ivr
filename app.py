import os
from flask import Flask, request, jsonify
import openai
import json

app = Flask(__name__)

# Set your OpenAI API key securely via Render environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        # Get JSON data from the incoming POST request
        data = request.get_json()
        print("DEBUG - Incoming data:", data)

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
                        "Extract booking information from the customer. "
                        "Return a valid JSON object ONLY with the following keys: "
                        "name, pickup_address, dropoff_address, date, time. "
                        "If any detail is missing, set its value to null. "
                        "Do NOT return any explanation, just the raw JSON."
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

        # Attempt to parse JSON response
        parsed_data = json.loads(ai_reply)
        return jsonify(parsed_data), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
