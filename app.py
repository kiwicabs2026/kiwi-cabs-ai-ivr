from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["POST"])
def process_input():
    data = request.get_json()
    speech_input = data.get("speech_input", "")

    # Simulate AI logic (or replace with OpenAI result later)
    full_text = f"You said: {speech_input}"

    # Break into chunks of max 29 characters
    chunk_size = 29
    chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]

    # Join chunks with short pauses (Twilio reads ". " as a pause)
    safe_reply = ". ".join(chunks)

    return jsonify({"reply": safe_reply})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
