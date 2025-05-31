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
TAXICALLER_SUB = "*"  # Use actual sub if required

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        print("DEBUG - Incoming data:", data)

        inputs = [
            data.get("widgets", {}).get("gather_trip_details", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_modify_voice", {}).get("SpeechResult", ""),
            data.get("widgets", {}).get("gather_cancel_voice", {}).get("SpeechResult", "")
        ]
        prompt = " ".join([text for text in inputs if text]).strip()
        print("DEBUG - Combined Prompt:", prompt)

        if "after tomorrow" in prompt.lower():
            day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\bafter tomorrow\\b", day_after, prompt, flags=re.IGNORECASE)

        if "tomorrow" in prompt.lower():
            tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            prompt = re.sub(r"\\btomorrow\\b", tomorrow_date, prompt, flags=re.IGNORECASE)

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
                        "You are based in New Zealand and must understand New Zealand accents.\n"
                        "Only accept pickup and drop-off addresses located in the Wellington region of New Zealand.\n"
                        "If the pickup or drop-off location is outside the Wellington region, respond with: 'Sorry, Kiwi Cabs only operates in the Wellington region of New Zealand.' Do not continue with the booking.\n"
                        "Use the NZ date/time format: 'dd/mm/yyyy HH:MM' (e.g., 31/05/2025 15:00).\n"
                        "You assist with taxi bookings, modifying details, or cancellations.\n"
                        "Your job is to extract all required information: name, pickup address, drop-off address, and exact date/time.\n"
                        "Only respond in valid JSON format like:\n"
                        "{'name': 'Sam', 'pickup': '27 Rex Street', 'dropoff': 'Wellington Hospital', 'time': '31/05/2025 15:00'}\n"
                        "If the time is vague (e.g. 'tomorrow', 'afternoon', 'evening'), clearly respond:\n"
                        "Could you please give me the exact date and time? For example, say something like '31 May at 9:00 PM'.\n"
                        "If the user says 'now' or 'right away', use the current exact time immediately and continue without asking again.\n"
                        "Never guess vague times. Never confirm bookings unless all fields are complete and valid.\n"
                        "After confirming the booking details, ask: 'Shall I confirm this booking? Please say yes or no.'\n"
                        "If the user says 'yes', proceed. If 'no', ask them to repeat the correct details.\n"
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

        if prompt.strip().lower() in ["yes", "yeah", "confirm"]:
            return jsonify({"reply": "Your taxi has been confirmed and dispatched. Thank you!"}), 200

        elif prompt.strip().lower() in ["no", "nope", "change", "wrong"]:
            return jsonify({"reply": "Okay, let’s update your booking. Please repeat your details."}), 200

        try:
            parsed = json.loads(ai_reply)
            print("Parsed JSON:", parsed)

            confirmation_prompt = (
                f"Please confirm your booking details:\n"
                f"Name: {parsed['name']}\n"
                f"Pickup: {parsed['pickup']}\n"
                f"Drop-off: {parsed['dropoff']}\n"
                f"Time: {parsed['time']}\n"
                f"Say 'yes' to confirm, or 'no' to make changes."
            )

            return jsonify({"confirmation": confirmation_prompt}), 200

        except json.JSONDecodeError:
            return jsonify({"reply": ai_reply}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
