import os
import json
from flask import Flask, request, jsonify, make_response
import openai
from datetime import datetime

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Session memory store
user_sessions = {}

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    print("DEBUG - Incoming data:", data)

    # Combine speech input
    inputs = [
        data.get("widgets", {}).get("gather_trip_details", {}).get("SpeechResult", ""),
        data.get("widgets", {}).get("gather_modify_voice", {}).get("SpeechResult", ""),
        data.get("widgets", {}).get("gather_cancel_voice", {}).get("SpeechResult", "")
    ]
    speech_result = " ".join([text for text in inputs if text]).strip()
    print("DEBUG - Combined SpeechResult:", speech_result)

    caller = data.get("user", {}).get("phone", "unknown")
    session = user_sessions.setdefault(caller, {"step": "menu", "flow": ""})

    current_step = session["step"]
    current_flow = session["flow"]

    # Simple menu handling
    if current_step == "menu":
        if "book" in speech_result.lower():
            session["flow"] = "new_booking"
            session["step"] = "collect_details"
        elif "modify" in speech_result.lower() or "update" in speech_result.lower():
            session["flow"] = "modify_booking"
            session["step"] = "find_booking"
        elif "speak" in speech_result.lower() or "team" in speech_result.lower():
            return jsonify({"action": "transfer", "message": "Transferring you to a team member."})
        else:
            return jsonify({"action": "prompt", "message": "Please say: book a taxi, modify a booking, or speak to a team member."})

    if current_flow == "new_booking":
        if current_step == "collect_details":
            full_prompt = replace_date_keywords(speech_result)
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful AI assistant for Kiwi Cabs.\n"
                                "IMPORTANT: Kiwi Cabs ONLY operates in Wellington region, New Zealand. "
                                "If pickup or destination is outside Wellington region, return: "
                                '{"error": "outside_wellington", "message": "We only operate in Wellington region"}'
                                "\nOtherwise, extract booking details and return ONLY a JSON object with these exact keys:\n"
                                "{\n"
                                '  "name": "customer name",\n'
                                '  "pickup": "pickup location",\n'
                                '  "dropoff": "destination",\n'
                                '  "time": "pickup time/date"\n'
                                "}\n"
                                "If any field is missing, set its value to 'missing'."
                            )
                        },
                        {"role": "user", "content": full_prompt}
                    ]
                )
                ai_reply = response.choices[0].message.content.strip()
                print("AI Reply:", ai_reply)

                parsed = json.loads(ai_reply)

                if "error" in parsed:
                    return jsonify({"action": "error", "message": parsed.get("message", "Invalid request.")})

                # Save details
                session.update(parsed)
                session["step"] = "confirm"

                return jsonify({
                    "action": "confirm",
                    "message": f"Your taxi from {parsed['pickup']} to {parsed['dropoff']} at {parsed['time']}. Say yes to confirm or no to update."
                })

            except Exception as e:
                print("AI ERROR:", e)
                return jsonify({"action": "error", "message": "Sorry, I had trouble understanding. Please try again."})

        elif current_step == "confirm":
            if "yes" in speech_result.lower():
                # Normally this would post to TaxiCaller
                session["step"] = "done"
                return jsonify({"action": "done", "message": "Thank you. Your taxi has been booked."})
            elif "no" in speech_result.lower():
                session["step"] = "collect_details"
                return jsonify({"action": "prompt", "message": "Let’s update your booking. Please say pickup and drop-off again."})
            else:
                return jsonify({"action": "prompt", "message": "Please say yes to confirm or no to update."})

    return jsonify({"action": "prompt", "message": "Let’s start again. Please say: book a taxi, modify a booking, or speak to a team member."})

def replace_date_keywords(text):
    today = datetime.now()
    tomorrow = today.replace(day=today.day + 1)
    return (
        text.replace("today", today.strftime("%d %B"))
            .replace("tomorrow", tomorrow.strftime("%d %B"))
    )

if __name__ == "__main__":
    app.run(debug=True)
