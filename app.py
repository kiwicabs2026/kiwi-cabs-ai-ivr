from flask import Flask, request, jsonify
import openai
import os
import json

# Create Flask app instance
app = Flask(__name__)

# Load OpenAI API key from environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Test route to confirm server is running
@app.route("/", methods=["GET", "HEAD"])
def home():
    return jsonify({"message": "Kiwi Cabs AI API is running"}), 200

# Main AI chat route
@app.route("/ask", methods=["POST"])
def ask():
    try:
        # Get JSON data from POST request
        data = request.get_json()

        # Get the prompt from request
        prompt = data.get("prompt", "").strip()

        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        # Call OpenAI Chat API
        response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {
            "role": "system",
            "content": (
                "You are a helpful taxi booking assistant for Kiwi Cabs. "
                "You are allowed to simulate booking taxis. "
                "When given a name, pickup address, drop-off address, and time, confirm the booking clearly. "
                "Speak directly to the customer like a real booking assistant."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
)


        # Extract the assistant's reply
        reply = response["choices"][0]["message"]["content"].strip()

        # Return reply in JSON
        return jsonify({"reply": reply}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Do NOT add app.run() here – Render will handle running the app using gunicorn
