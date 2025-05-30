import os
import json
from flask import Flask, request, jsonify, session
import openai
from datetime import datetime, timedelta
import re
import requests

app = Flask(__name__)
app.secret_key = "any-random-string"
openai.api_key = os.getenv("OPENAI_API_KEY")

# TaxiCaller credentials
TAXICALLER_API_KEY = "c18afde179ec057037084b4daf10f01a"
TAXICALLER_SUB = "*"

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

        # Replace vague date terms
        if "after tomorrow" in prompt.lower():
            day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\bafter tomorrow\\b", day_after, prompt, flags=re.IGNORECASE)
        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btomorrow\\b", tomorrow_date, prompt, flags=re.IGNORECASE)
        if "today" in prompt.lower():
            today_date = datetime.now().strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btoday\\b", today_date, prompt, flags=re.IGNORECASE)

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
                        "Please say 'yes' to confirm or 'no' to update.\n"
                        "If the time or date is missing or unclear, ask the user to provide an exact date and time like '31 May at 3:00 PM'.\n"
                        "If the user says 'now' or 'right away', use the current exact time immediately and continue without asking again.\n"
                        "Reject addresses outside the Wellington region and inform the user.\n"
                        "Do not mention notifications or ask if they need anything else."
                    )
                },
                {"role": "user", "content": prompt}
            ]
        )

        ai_reply = response["choices"][0]["message"]["content"].strip()
        print("AI RAW REPLY:", ai_reply)

        try:
            parsed = json.loads(ai_reply)
            print("Parsed JSON:", parsed)

            confirmation = parsed.get("confirmation", "").lower()

            if confirmation == "yes":
                parsed = session.get("last_booking")
                if not parsed:
                    return jsonify({"reply": "Sorry, I don’t have your previous booking. Please repeat the details."}), 200
            elif confirmation == "no":
                return jsonify({"reply": "Sure, let's update your booking. Please provide the correct details."}), 200
            elif confirmation != "yes":
                session['last_booking'] = parsed  # store booking info temporarily
                confirmation_prompt = (
                    f"Hello {parsed.get('name')}, your Kiwi Cab has been scheduled. Here are the details:\n"
                    f"Pick-up: {parsed.get('pickup')}\n"
                    f"Drop-off: {parsed.get('dropoff')}\n"
                    f"Time: {parsed.get('time')}\n"
                    "Please say 'yes' to confirm or 'no' to update."
                )
                return jsonify({"reply": confirmation_prompt}), 200

            pickup_time = parsed["time"]
            if pickup_time.strip().lower() in ["now", "right away"]:
                pickup_datetime = datetime.now()
            else:
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

            token_url = f"https://api-rc.taxicaller.net/api/v1/jwt/for-key?key={TAXICALLER_API_KEY}&sub={TAXICALLER_SUB}"
            token_response = requests.get(token_url)
            if token_response.status_code != 200:
                raise Exception(f"Failed to get token: {token_response.status_code} {token_response.text}")

            bearer_token = token_response.json().get("token")
            if not bearer_token:
                raise ValueError("Token not found in response")

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
