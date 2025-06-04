from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
import openai
import json
import os

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET"])
def home():
    return "Kiwi Cabs AI IVR is running."

# In-memory session store
user_sessions = {}

def make_twiml_speech_response(text):
    response = VoiceResponse()
    gather = Gather(input="speech", action="/process_speech", method="POST", timeout=5)
    gather.say(text, language="en-NZ")
    response.append(gather)
    response.redirect("/voice")
    return str(response)

@app.route("/voice", methods=["POST"])
def voice():
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/menu",
        method="POST",
        timeout=5,
        hints="option one, option two, option three"
    )
    gather.say(
        """
        <speak>
        Kia ora, and welcome to Kiwi Cabs.
        I am your A. I. assistant — artificial intelligence assistant — here to help you book your taxi.
        This call may be recorded for training and security purposes.
        Please listen carefully and respond clearly.
        Say option one to book a taxi.
        Say option two to change or cancel an existing booking.
        Say option three to speak to a team member.
        I'm listening.
        </speak>
        """,
        language="en-NZ"
    )
    response.append(gather)
    response.redirect("/voice")
    return str(response)

@app.route("/menu", methods=["POST"])
def menu():
    speech_result = request.form.get("SpeechResult", "").strip().lower()
    caller = request.form.get("From", "caller")

    if "1" in speech_result or "one" in speech_result:
        user_sessions[caller] = {"step": "collect_details"}
        return make_twiml_speech_response("Please tell me your name, pickup location, destination, and time.")

    elif "2" in speech_result or "two" in speech_result:
        return make_twiml_speech_response("Please say the phone number used for your booking and the new time or date you want.")

    elif "3" in speech_result or "three" in speech_result:
        response = VoiceResponse()
        response.say("Please wait while we connect you to our office.", language="en-NZ")
        response.dial("+648966156")
        return str(response)

    else:
        return make_twiml_speech_response("Sorry, I didn’t get that. Please say option one, two, or three.")

@app.route("/process_speech", methods=["POST"])
def process_speech():
    speech = request.form.get("SpeechResult", "")
    caller = request.form.get("From", "caller")
    session = user_sessions.setdefault(caller, {})
    step = session.get("step", "collect_details")

    if step == "collect_details":
        try:
            ai_response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant for Kiwi Cabs in Wellington, New Zealand. IMPORTANT: We only operate within Wellington region. If pickup or dropoff is outside Wellington, reply with {\"error\": \"outside_wellington\", \"message\": \"Sorry, we only operate in Wellington region.\"}. Otherwise, return JSON: {\"name\", \"pickup\", \"dropoff\", \"time\"}."},
                    {"role": "user", "content": speech}
                ]
            )
            reply = ai_response.choices[0].message.content.strip()
            parsed = json.loads(reply)

            if "error" in parsed:
                return make_twiml_speech_response(parsed["message"])

            session.update(parsed)
            session["step"] = "confirm"
            user_sessions[caller] = session

            return make_twiml_speech_response(
                f"Let me confirm your booking. From {parsed['pickup']} to {parsed['dropoff']} at {parsed['time']}. Say yes to confirm or no to change."
            )

        except Exception as e:
            print("AI ERROR:", e)
            return make_twiml_speech_response("Sorry, I couldn't understand. Please try again.")

    elif step == "confirm":
        if "yes" in speech.lower():
            booking_data = {key: session[key] for key in ["name", "pickup", "dropoff", "time"] if key in session}
            try:
                import requests
                requests.post("https://your-render-url/submit", json=booking_data)
            except:
                pass
            return make_twiml_speech_response("Thanks. Your taxi has been booked.")

        elif "no" in speech.lower():
            session["step"] = "collect_details"
            return make_twiml_speech_response("Okay, let's try again. Please say your name, pickup, dropoff, and time.")

        else:
            return make_twiml_speech_response("Please say yes to confirm or no to update.")

    return make_twiml_speech_response("Let's start again. Please say your booking details.")

if __name__ == '__main__':
    app.run(debug=True)
