import os
import json
from flask import Flask, request, jsonify, make_response
import openai
from datetime import datetime

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Memory for sessions
user_sessions = {}

# Replace keywords like "tomorrow" with actual dates
def replace_date_keywords(text):
    today = datetime.now()
    tomorrow = today.replace(day=today.day + 1)
    return (
        text.replace("today", today.strftime("%d %B"))
            .replace("tomorrow", tomorrow.strftime("%d %B"))
    )

@app.route("/ask", methods=["POST"])
def ask():
    data = request.form
    print("DEBUG - Incoming data:", data)

    inputs = [
        data.get("SpeechResult", "")
    ]

    speech_result = " ".join([text for text in inputs if text]).strip()
    print("DEBUG - Combined SpeechResult:", speech_result)

    caller = data.get("From", "unknown")
    session = user_sessions.setdefault(caller, {"step": "menu", "flow": ""})
    current_step = session["step"]
    current_flow = session["flow"]

    # Main Menu - Initial greeting with options
    if current_step == "menu":
        greeting = (
            "Kia ora, and welcome to Kiwi Cabs. "      
            "I'm an A.I. assistant and I understand what you say. "
            "This call may be recorded for training and security purposes. "
            "Press 1 to book a new taxi, Press 2 to modify or cancel an existing booking, or Press 3 to speak to a team member."
        )
        session["step"] = "menu_waiting"
        return make_twiml_dtmf_response(greeting)

    if current_step == "menu_waiting":
        digits = data.get("Digits", "")
        if digits == "1":
            session["flow"] = "new_booking"
            session["step"] = "collect_details"
            return make_twiml_speech_response("Please tell me your name, pickup location, destination, and pickup time.")
        elif digits == "2":
            session["flow"] = "modify_booking"
            session["step"] = "find_booking"
            return make_twiml_speech_response("Say 'modify' to change your booking, or 'cancel' to cancel it.")
        elif digits == "3":
            return make_twiml_response("Transferring you to a team member.", action="transfer")
        else:
            return make_twiml_dtmf_response("Invalid selection. Please press 1, 2, or 3.")

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
                                "IMPORTANT: Kiwi Cabs ONLY operates in Wellington region, New Zealand.\n"
                                "If pickup or destination is outside Wellington region, return: {\"error\": \"outside_wellington\", \"message\": \"We only operate in Wellington region\"}\n"
                                "Otherwise, extract booking details and return ONLY a JSON object with these keys: {\"name\", \"pickup\", \"dropoff\", \"time\"}"
                            )
                        },
                        {"role": "user", "content": full_prompt}
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
                return make_twiml_response("Thank you. Your taxi has been booked. Your reference is your phone number.")
            elif "no" in speech_result.lower():
                session["step"] = "collect_details"
                return make_twiml_speech_response("No problem. Please repeat your name, pickup location, destination, and time.")
            else:
                return make_twiml_speech_response("Please say 'yes' to confirm or 'no' to update.")

    if current_flow == "modify_booking":
        if current_step == "find_booking":
            # The phone number is the reference
            if caller not in user_sessions:
                return make_twiml_response("No booking found under your number. Goodbye.")
            if "cancel" in speech_result.lower():
                user_sessions.pop(caller)
                return make_twiml_response("Your booking has been cancelled.")
            elif "modify" in speech_result.lower():
                session["step"] = "collect_details"
                return make_twiml_speech_response("Please say the updated pickup, dropoff, and time.")
            else:
                return make_twiml_speech_response("Say 'modify' or 'cancel'.")

    return make_twiml_speech_response("Sorry, something went wrong. Please call again.")

def make_twiml_response(message, action=None):
    if action == "transfer":
        return make_response(f"""
        <Response>
            <Say voice="Polly.Aria-Neural">{message}</Say>
            <Dial>+6441234567</Dial>
        </Response>
        """, 200, {"Content-Type": "application/xml"})
    return make_response(f"""
    <Response>
        <Say voice="Polly.Aria-Neural">{message}</Say>
    </Response>
    """, 200, {"Content-Type": "application/xml"})

def make_twiml_speech_response(message):
    return make_response(f"""
    <Response>
        <Gather input="speech" action="/ask" method="POST">
            <Say voice="Polly.Aria-Neural">{message}</Say>
        </Gather>
    </Response>
    """, 200, {"Content-Type": "application/xml"})

def make_twiml_dtmf_response(message):
    return make_response(f"""
    <Response>
        <Gather input="dtmf" timeout="10" numDigits="1" action="/ask" method="POST">
            <Say voice="Polly.Aria-Neural">{message}</Say>
        </Gather>
        <Say voice="Polly.Aria-Neural">Sorry, I didn’t receive a response. Please call again.</Say>
    </Response>
    """, 200, {"Content-Type": "application/xml"})

if __name__ == "__main__":
    app.run(debug=True)
