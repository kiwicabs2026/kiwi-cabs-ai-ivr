import os
import json
from flask import Flask, request, jsonify
import openai
from datetime import datetime, timedelta
import re  # Needed for replacing 'tomorrow' accurately

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        print("DEBUG - Incoming data:", data)

        # Combine speech input from all widgets
        inputs = [
            data.get("widgets", {}).get("gather_trip_details", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_modify_voice", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_cancel_voice", {}).get("SpeechResult", "")
        ]
        prompt = " ".join([text for text in inputs if text]).strip()
        print("DEBUG - Combined Prompt:", prompt)

        # Replace 'tomorrow' with formatted NZ date using regex
        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\btomorrow\b", tomorrow_date, prompt, flags=re.IGNORECASE)
            print("DEBUG - Updated Prompt with NZ date:", prompt)

        if not prompt:
            return jsonify({"reply": "Sorry, I didn’t catch that. Could you please repeat your booking details?"}), 200

        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant for Kiwi Cabs.\n"
                        "You assist with taxi bookings, modifying details, or cancellations.\n"
                        "When the user provides name, pickup address, destination, and time/date, confirm like this:\n"
                        "Hello [Name], your Kiwi Cab has been scheduled. Here are the details:\n"
                        "Pick-up: [Pickup Address]\n"
                        "Drop-off: [Dropoff Address]\n"
                        "Time: [Time and Date]\n"
                        "Thank you for choosing Kiwi Cabs.\n"
                        "Do not mention notifications or ask if they need anything else."
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

        try:
            parsed = json.loads(ai_reply)
            print("Parsed JSON:", parsed)
            return jsonify(parsed), 200
        except json.JSONDecodeError:
            return jsonify({"reply": ai_reply}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
