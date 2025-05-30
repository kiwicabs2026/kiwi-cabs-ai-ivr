import os
import json
from flask import Flask, request, jsonify
import openai
from datetime import datetime, timedelta
import re
import requests

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# TaxiCaller credentials
TAXICALLER_API_KEY = "c18afde179ec057037084b4daf10f01a"
TAXICALLER_SUB = "*"  # Can be updated to actual sub if needed

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        print("DEBUG - Incoming data:", data)

        # Combine speech input
        inputs = [
            data.get("widgets", {}).get("gather_trip_details", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_modify_voice", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_cancel_voice", {}).get("SpeechResult", "")
        ]
        prompt = " ".join([text for text in inputs if text]).strip()
        print("DEBUG - Combined Prompt:", prompt)

        # Replace date keywords
        if "after tomorrow" in prompt.lower():
            day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\bafter tomorrow\b", day_after, prompt, flags=re.IGNORECASE)

        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\btomorrow\b", tomorrow_date, prompt, flags=re.IGNORECASE)

        print("DEBUG - Final Prompt with replaced date:", prompt)

        if not prompt:
            return jsonify({"reply": "Sorry, I didn’t catch that. Could you please repeat your booking details?"}), 200

        # OpenAI call
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

            pickup_time = parsed["time"]
            pickup_datetime = datetime.strptime(pickup_time, "%d/%m/%Y %H:%M")
            iso_time = pickup_datetime.isoformat()

            job_data = {
                "job": {
                    "pickup": {"address": parsed["pickup"]},
                    "dropoff": {"address": parsed["dropoff"]},
                    "time": iso_time,
                    "client": {"name": parsed["name"]}
                }
            }

            # Get Bearer token first
            token_url = f"https://api-rc.taxicaller.net/api/v1/jwt/for-key?key={TAXICALLER_API_KEY}&sub={TAXICALLER_SUB}"
            token_response = requests.get(token_url)
            if token_response.status_code != 200:
                raise Exception(f"Failed to get token: {token_response.status_code} {token_response.text}")

            bearer_token = token_response.json().get("token")
            if not bearer_token:
                raise ValueError("Token not found in response")

            # Send booking to TaxiCaller
            response = requests.post(
                "https://api-rc.taxicaller.net/api/v1/book/order",
                json=job_data,
                headers={
                    "Authorization": f"Bearer {bearer_token}",
                    "Content-Type": "application/json"
                }
            )

            print("TAXICALLER RESPONSE:", response.text)
            return jsonify(parsed), 200

        except json.JSONDecodeError:
            return jsonify({"reply": ai_reply}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
