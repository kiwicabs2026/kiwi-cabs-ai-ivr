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
                    "content": "You are an AI assistant extracting booking details for a taxi. Reply ONLY with a JSON like this: {\"pickup_address\": \"123 ABC St\", \"dropoff_address\": \"Wellington Airport\", \"pickup_datetime\": \"5 PM today\"}."
                },
                {"role": "user", "content": speech_input}
            ]
        )

        # Try to parse the returned text as JSON
        ai_reply = completion.choices[0].message.content.strip()
        parsed_data = json.loads(ai_reply)

        return jsonify(parsed_data)

    except Exception as e:
        return jsonify({"reply": "There was a problem replying."})
