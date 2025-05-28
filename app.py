from flask import Flask, request, jsonify
import openai
import os

app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET"])
def home():
    return "Kiwi Cabs AI IVR is running!"

@app.route("/process-booking", methods=["POST"])
def process_booking():
    data = request.get_json()
    user_input = data.get("message", "")

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You're an assistant for a taxi booking service."},
            {"role": "user", "content": user_input}
        ]
    )

    return jsonify({"response": response.choices[0]["message"]["content"]})

if __name__ == "__main__":
    app.run(debug=True)
