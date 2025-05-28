from flask import Flask, request, jsonify
import openai
import os

app = Flask(__name__)
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/", methods=["GET", "HEAD"])
def health_check():
    return jsonify({"message": "Kiwi Cabs AI API is running"}), 200

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "").strip()

        if not prompt:
            return jsonify({"reply": "Sorry, I didn’t hear anything. Please say your name, pickup, drop-off, and time again."}), 200

        print("📥 Prompt received:", prompt)

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful taxi booking assistant for Kiwi Cabs. "
                        "You are allowed to simulate booking taxis. "
                        "When given a name, pickup address, drop-off address, and time, confirm the booking clearly. "
                        "Respond in one polite sentence, like a real assistant."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        reply = response["choices"][0]["message"]["content"].strip()

        print("🤖 AI reply:", reply)
        return jsonify({"reply": reply}), 200

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"reply": "Sorry, something went wrong while processing your booking. Please try again."}), 200
