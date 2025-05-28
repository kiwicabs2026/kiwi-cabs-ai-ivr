from flask import Flask, request, jsonify
import openai
import os
import json

app = Flask(__name__)
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/", methods=["POST"])
def process_input():
    data = request.get_json()
    speech_input = data.get("speech_input", "")

    if not speech_input:
        return jsonify({"reply": "Sorry, I didn't catch that."})

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict AI that extracts only booking details for a taxi. "
                        "Reply ONLY with this JSON format: "
                        '{ "pickup_address": "...", "dropoff_address": "...", "pickup_datetime": "..." }. '
                        "Do not add any text, explanation, or greetings."
                    )
                },
                {"role": "user", "content": speech_input}
            ]
        )

        ai_reply = completion.choices[0].message.content.strip()
        parsed_data = json.loads(ai_reply)  # must be valid JSON

        return jsonify(parsed_data)

    except Exception as e:
        return jsonify({"reply": "There was a problem replying."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
