import os
import json
from flask import Flask, request, jsonify
import openai

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Dummy session store
user_sessions = {}

def sanitize_asr_errors(text):
    return text.replace("to morrow", "tomorrow").replace("Welly", "Wellington")

def replace_date_keywords(text):
    return text  # Add your real logic here if needed

def make_twiml_speech_response(text):
    return jsonify({"say": text})

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()

    # Simulated input routing
    current_flow = data.get("flow", "new_booking")
    current_step = data.get("step", "collect_details")
    speech_result = data.get("speech", "")

    # Dummy user session
    session = user_sessions.setdefault(data.get("session_id", "default"), {})

    if current_flow == "new_booking":
        if current_step == "collect_details":
            sanitized = sanitize_asr_errors(speech_result)
            full_prompt = replace_date_keywords(sanitized)
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful AI assistant for Kiwi Cabs.\n"
                                "IMPORTANT: Kiwi Cabs ONLY operates in Wellington region, New Zealand.\n"
                                "If pickup or destination is outside Wellington region, return: {\"error\": \"outside_wellington\", \"message\": \"Sorry, we only operate in Wellington region.\"}\n"
                                "Otherwise, extract booking details and return ONLY a JSON object with these keys: {\"name\", \"pickup\", \"dropoff\", \"time\"}."
                            )
                        },
                        {
                            "role": "user",
                            "content": full_prompt
                        }
                    ]
                )
                ai_reply = response.choices[0].message.content.strip()
                parsed = json.loads(ai_reply)

                if "error" in parsed:
                    return make_twiml_speech_response(parsed["message"])

                session.update(parsed)
                session["step"] = "confirm"
                return make_twiml_speech_response(
                    f"Let me confirm your booking. From {parsed['pickup']} to {parsed['dropoff']} at {parsed['time']}. Say 'yes' to confirm or 'no' to update."
                )

            except Exception as e:
                print("AI ERROR:", e)
                return make_twiml_speech_response("Sorry, I couldn't understand your booking. Please try again.")

        if current_step == "confirm":
            if "yes" in speech_result.lower():
                session["step"] = "done"
                return make_twiml_speech_response("Thank you. Your taxi has been booked. Your reference is your phone number.")
            elif "no" in speech_result.lower():
                session["step"] = "collect_details"
                return make_twiml_speech_response("No problem. Please repeat your name, pickup location, destination, and time.")
            else:
                return make_twiml_speech_response("Please say 'yes' to confirm or 'no' to update.")

    return make_twiml_speech_response("Unhandled flow or step.")
