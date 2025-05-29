import os
from flask import Flask, request, jsonify
import openai

app = Flask(__name__)

# Set your OpenAI API key securely via Render environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        # Get JSON data from the POST request
        data = request.get_json()

        # Extract 'prompt' from incoming payload (expected from Twilio)
        prompt = data.get("prompt", "").strip()

        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        # Call OpenAI ChatCompletion
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful taxi booking assistant for Kiwi Cabs. "
                        "You are allowed to simulate booking, modifying, or canceling taxis. "
                        "When the user gives name, pickup address, destination, and time/date, "
                        "respond clearly confirming the job. Speak naturally like a real assistant."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extract the AI's reply
        reply = response["choices"][0]["message"]["content"].strip()

        # Return it as JSON for Twilio Studio to read
        return jsonify({"reply": reply}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
