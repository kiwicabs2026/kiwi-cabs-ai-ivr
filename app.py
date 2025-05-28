from flask import Flask, request, jsonify
import openai
import os

app = Flask(__name__)

# Load the OpenAI key securely from environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/", methods=["POST"])
def process_input():
    data = request.get_json()
    speech_input = data.get("speech_input", "")

    if not speech_input:
        return jsonify({"reply": "Sorry, I didn't catch that."})

    # Send input to OpenAI GPT-4
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a helpful AI assistant taking taxi bookings by voice."},
                {"role": "user", "content": speech_input}
            ]
        )
        reply = completion.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"reply": "There was a problem replying."})

    # Split reply into <=29-character chunks for Twilio speech
    chunk_size = 29
    chunks = [reply[i:i+chunk_size] for i in range(0, len(reply), chunk_size)]
    safe_reply = ". ".join(chunks)

    return jsonify({"reply": safe_reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

