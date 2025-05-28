from flask import Flask, request, jsonify
import openai
import os

app = Flask(__name__)
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/", methods=["GET", "HEAD"])
def health_check():
    return jsonify({"message": "Kiwi Cabs AI API is running"}), 200

@app.route@app.route("/ask", methods=["POST"])
def ask():
    try:
        print("🔧 Incoming request")

        data = request.get_json(force=True)
        print("📦 Raw data received:", data)

        prompt = data.get("prompt", "").strip()
        print("📝 Extracted prompt:", prompt)

        if not prompt:
            return jsonify({"reply": "Sorry, I didn’t hear anything. Please try again."}), 200

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful taxi booking assistant for Kiwi Cabs. "
                        "You are allowed to simulate booking taxis. "
                        "When given a name, pickup address, drop-off address, and time, confirm the booking clearly."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        reply = response["choices"][0]["message"]["content"].strip()
        print("✅ GPT Reply:", reply)

        return jsonify({"reply": reply}), 200

    except Exception as e:
        print("❌ Exception:", str(e))
        return jsonify({"reply": "Internal error: " + str(e)}), 200

