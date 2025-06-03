from flask import Flask, request, make_response
import openai
import os
import json
from datetime import datetime, timedelta
import re

app = Flask(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Memory stores
user_sessions = {}
bookings = {}  # Store confirmed bookings by phone number

def twiml_response_with_gather(text, timeout=10):
    """Use this for prompts that need user response"""
    return f"""
    <Response>
        <Gather input="speech" action="/ask" method="POST" timeout="{timeout}">
            <Say voice="Polly.Aria-Neural">{text}</Say>
        </Gather>
        <Say voice="Polly.Aria-Neural">Sorry, I didn't hear a response. Please call back. Goodbye.</Say>
    </Response>
    """

def twiml_response_with_dtmf_gather(text, timeout=10):
    """Use this for menu options that need DTMF input"""
    return f"""
    <Response>
        <Gather input="dtmf" action="/ask" method="POST" timeout="{timeout}" numDigits="1">
            <Say voice="Polly.Aria-Neural">{text}</Say>
        </Gather>
        <Say voice="Polly.Aria-Neural">Sorry, I didn't receive a selection. Please call back. Goodbye.</Say>
    </Response>
    """

def twiml_response(text):
    """Use this for final messages that end the call"""
    return f"""
    <Response>
        <Say voice="Polly.Aria-Neural">{text}</Say>
    </Response>
    """

def replace_date_keywords(prompt):
    """Replace relative date keywords with actual dates"""
    if "after tomorrow" in prompt.lower():
        day_after = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
        prompt = re.sub(r"\bafter tomorrow\b", day_after, prompt, flags=re.IGNORECASE)
    if "tomorrow" in prompt.lower():
        tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        prompt = re.sub(r"\btomorrow\b", tomorrow_date, prompt, flags=re.IGNORECASE)
    if "today" in prompt.lower():
        today_date = datetime.now().strftime("%d/%m/%Y")
        prompt = re.sub(r"\btoday\b", today_date, prompt, flags=re.IGNORECASE)
    return prompt

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_id = request.form.get("From", "default_user")
        speech_result = request.form.get("SpeechResult")
        digits = request.form.get("Digits")
        
        print(f"DEBUG - User: {user_id}, Speech: {speech_result}, Digits: {digits}")
        
        # STEP 1: First call - show main menu
        if not speech_result and not digits:
            menu_text = """
                Kia ora, and welcome to Kiwi Cabs.
                <break time="400ms"/>
                I'm an A.I. assistant and I understand what you say.
                <break time="500ms"/>
                This call may be recorded for training and security purposes.
                <break time="600ms"/>
                Press 1 to book a new taxi, or Press 2 to modify or cancel an existing booking.
            """
            response = make_response(twiml_response_with_dtmf_gather(menu_text, 15))
            response.headers["Content-Type"] = "application/xml"
            return response
        
        # STEP 2: Handle menu selection
        if digits:
            if digits == "1":
                # New booking flow
                user_sessions[user_id] = {"flow": "new_booking", "step": "collect_details"}
                gather_text = "Please tell me your name, pickup location, destination, and pickup time."
                response = make_response(twiml_response_with_gather(gather_text))
                response.headers["Content-Type"] = "application/xml"
                return response
                
            elif digits == "2":
                # Modify booking flow
                user_sessions[user_id] = {"flow": "modify_booking", "step": "get_reference"}
                if user_id in bookings:
                    gather_text = f"I found your existing booking. Say 'modify' to change the time or date, or say 'cancel' to cancel your booking."
                else:
                    gather_text = "I couldn't find any existing booking with your phone number. Would you like to make a new booking instead? Say 'yes' for new booking."
                response = make_response(twiml_response_with_gather(gather_text))
                response.headers["Content-Type"] = "application/xml"
                return response
            else:
                response = make_response(twiml_response("Invalid selection. Please call back and press 1 or 2. Goodbye."))
                response.headers["Content-Type"] = "application/xml"
                return response
        
        # STEP 3: Handle speech input
        if not speech_result:
            response = make_response(twiml_response("Sorry, I didn't catch that. Please call back and try again. Goodbye."))
            response.headers["Content-Type"] = "application/xml"
            return response
        
        prompt = speech_result.strip().lower()
        user_session = user_sessions.get(user_id, {})
        current_flow = user_session.get("flow", "")
        current_step = user_session.get("step", "")
        
        print(f"DEBUG - Flow: {current_flow}, Step: {current_step}, Prompt: {prompt}")
        
        # Handle NEW BOOKING flow
        if current_flow == "new_booking":

if current_step == "collect_details":
    # Process booking details with AI
    full_prompt = replace_date_keywords(speech_result)
           try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful AI assistant for Kiwi Cabs.\n"
                            "IMPORTANT: Kiwi Cabs ONLY operates in Wellington region, New Zealand. "
                            "This includes Wellington CBD, Newtown, Thorndon, Kelburn, Island Bay, Miramar, Petone, Lower Hutt, Upper Hutt, Porirua, Kapiti Coast, Johnsonville, and Tawa.\n"
                            "If pickup or destination is outside Wellington region, return: {\"error\": \"outside_wellington\", \"message\": \"We only operate in Wellington region\"}\n"
                            "Otherwise, extract booking details and return ONLY a JSON object with these exact keys:\n"
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


                    # Try to parse JSON
                    parsed = json.loads(ai_reply)
                    
                    # Check if location is outside Wellington
                    if parsed.get("error") == "outside_wellington":
                        user_sessions.pop(user_id, None)  # Clear session
                        sorry_text = "I'm sorry, but Kiwi Cabs only operates within Wellington region."
                        response = make_response(twiml_response(sorry_text))
                        response.headers["Content-Type"] = "application/xml"
                        return response
                    
                    # Check if all required fields are present
                    required_fields = ["name", "pickup", "dropoff", "time"]
                    missing_fields = [field for field in required_fields if parsed.get(field, "").lower() in ["missing", "", "not provided"]]
                    
                    if missing_fields:
                        missing_text = ", ".join(missing_fields)
                        gather_text = f"I need more information. Please provide your {missing_text}."
                        response = make_response(twiml_response_with_gather(gather_text))
                        response.headers["Content-Type"] = "application/xml"
                        return response
                    
                    # Store parsed data and ask for confirmation
                    user_sessions[user_id].update({"step": "confirm", "booking_data": parsed})
                    
                    confirmation_text = (
                        f"Let me confirm your booking. "
                        f"Name: {parsed['name']}. "
                        f"Pickup: {parsed['pickup']}. "
                        f"Destination: {parsed['dropoff']}. "
                        f"Time: {parsed['time']}. "
                        f"Say 'yes' to confirm or 'no' to change details."
                    )
                    
                    response = make_response(twiml_response_with_gather(confirmation_text, 15))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                    
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"JSON Error: {e}")
                    gather_text = "I didn't catch all the details. Please tell me your name, pickup location, destination, and pickup time again."
                    response = make_response(twiml_response_with_gather(gather_text))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                    
            elif current_step == "confirm":
                if any(word in prompt for word in ["yes", "yeah", "yep", "correct", "confirm"]):
                    # Confirm booking
                    booking_data = user_session.get("booking_data", {})
                    bookings[user_id] = {
                        **booking_data,
                        "reference": user_id,
                        "created_at": datetime.now().isoformat(),
                        "status": "confirmed"
                    }
                    
                    # Clear session
                    user_sessions.pop(user_id, None)
                    
                    final_text = f"Perfect! Your booking is confirmed, {booking_data.get('name')}. Your reference number is your phone number: {user_id}. A Kiwi Cab will pick you up at {booking_data.get('pickup')} at {booking_data.get('time')}. Thank you for choosing Kiwi Cabs!"
                    
                    response = make_response(twiml_response(final_text))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                    
                elif any(word in prompt for word in ["no", "nah", "change", "wrong"]):
                    # Go back to collect details
                    user_sessions[user_id]["step"] = "collect_details"
                    gather_text = "No problem. Please tell me your name, pickup location, destination, and pickup time again."
                    response = make_response(twiml_response_with_gather(gather_text))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                else:
                    gather_text = "Please say 'yes' to confirm your booking or 'no' to change the details."
                    response = make_response(twiml_response_with_gather(gather_text))
                    response.headers["Content-Type"] = "application/xml"
                    return response
        
        # Handle MODIFY BOOKING flow
        elif current_flow == "modify_booking":
            if current_step == "get_reference":
                if user_id in bookings:
                    existing_booking = bookings[user_id]
                    
                    if any(word in prompt for word in ["modify", "change", "update"]):
                        user_sessions[user_id]["step"] = "modify_details"
                        gather_text = f"Your current booking: Pickup at {existing_booking.get('pickup')} to {existing_booking.get('dropoff')} at {existing_booking.get('time')}. What would you like to change? Tell me the new pickup time, date, or location."
                        response = make_response(twiml_response_with_gather(gather_text))
                        response.headers["Content-Type"] = "application/xml"
                        return response
                        
                    elif any(word in prompt for word in ["cancel", "delete", "remove"]):
                        user_sessions[user_id]["step"] = "confirm_cancel"
                        gather_text = f"Are you sure you want to cancel your booking for pickup at {existing_booking.get('pickup')} at {existing_booking.get('time')}? Say 'yes' to cancel or 'no' to keep it."
                        response = make_response(twiml_response_with_gather(gather_text))
                        response.headers["Content-Type"] = "application/xml"
                        return response
                    else:
                        gather_text = "Please say 'modify' to change your booking details or 'cancel' to cancel your booking."
                        response = make_response(twiml_response_with_gather(gather_text))
                        response.headers["Content-Type"] = "application/xml"
                        return response
                else:
                    if any(word in prompt for word in ["yes", "yeah", "yep"]):
                        # Redirect to new booking
                        user_sessions[user_id] = {"flow": "new_booking", "step": "collect_details"}
                        gather_text = "Great! Please tell me your name, pickup location, destination, and pickup time."
                        response = make_response(twiml_response_with_gather(gather_text))
                        response.headers["Content-Type"] = "application/xml"
                        return response
                    else:
                        response = make_response(twiml_response("No problem. Thank you for calling Kiwi Cabs. Goodbye."))
                        response.headers["Content-Type"] = "application/xml"
                        return response
                        
            elif current_step == "modify_details":
                # Process modification with AI
                full_prompt = replace_date_keywords(speech_result)
                existing_booking = bookings[user_id]
                
                try:
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    f"You are updating a taxi booking for Kiwi Cabs. IMPORTANT: We ONLY operate in Wellington region, New Zealand.\n"
                                    f"If any new location mentioned is outside Wellington region, return: {{\"error\": \"outside_wellington\"}}\n"
                                    f"Current booking details:\n"
                                    f"Name: {existing_booking.get('name')}\n"
                                    f"Pickup: {existing_booking.get('pickup')}\n"
                                    f"Dropoff: {existing_booking.get('dropoff')}\n"
                                    f"Time: {existing_booking.get('time')}\n\n"
                                    "Update only the fields mentioned by the user. Return ONLY a JSON object with these exact keys:\n"
                                    "{\n"
                                    '  "name": "name (keep existing if not mentioned)",\n'
                                    '  "pickup": "pickup location (keep existing if not mentioned)",\n'
                                    '  "dropoff": "destination (keep existing if not mentioned)",\n'
                                    '  "time": "new time/date (keep existing if not mentioned)"\n'
                                    "}\n"
                                    "Wellington region includes: Wellington CBD, Newtown, Thorndon, Kelburn, Island Bay, Miramar, Petone, Lower Hutt, Upper Hutt, Porirua, Paraparaumu, Kapiti, Johnsonville, Tawa, and all Wellington suburbs."
                                )
                            },
                            {"role": "user", "content": full_prompt}
                        ]
                    )
                    
                    ai_reply = response.choices[0].message.content.strip()
                    updated_booking = json.loads(ai_reply)
                    
                    # Check if new location is outside Wellington
                    if updated_booking.get("error") == "outside_wellington":
                        gather_text = "I'm sorry, but Kiwi Cabs only operates within Wellington region."
                        response = make_response(twiml_response(gather_text))
                        response.headers["Content-Type"] = "application/xml"
                        return response
                    
                    # Store updated booking and ask for confirmation
                    user_sessions[user_id].update({"step": "confirm_modification", "updated_booking": updated_booking})
                    
                    confirmation_text = (
                        f"Let me confirm your updated booking. "
                        f"Name: {updated_booking['name']}. "
                        f"Pickup: {updated_booking['pickup']}. "
                        f"Destination: {updated_booking['dropoff']}. "
                        f"Time: {updated_booking['time']}. "
                        f"Say 'yes' to confirm changes or 'no' to try again."
                    )
                    
                    response = make_response(twiml_response_with_gather(confirmation_text, 15))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                    
                except (json.JSONDecodeError, KeyError):
                    gather_text = "I didn't understand what you'd like to change. Please tell me specifically what you want to update - the time, date, pickup location, or destination."
                    response = make_response(twiml_response_with_gather(gather_text))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                    
            elif current_step == "confirm_modification":
                if any(word in prompt for word in ["yes", "yeah", "yep", "correct", "confirm"]):
                    # Update the booking
                    updated_booking = user_session.get("updated_booking", {})
                    bookings[user_id].update(updated_booking)
                    bookings[user_id]["modified_at"] = datetime.now().isoformat()
                    
                    # Clear session
                    user_sessions.pop(user_id, None)
                    
                    response = make_response(twiml_response("Perfect! Your booking has been updated successfully. Thank you for choosing Kiwi Cabs!"))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                    
                elif any(word in prompt for word in ["no", "nah", "change", "wrong"]):
                    user_sessions[user_id]["step"] = "modify_details"
                    gather_text = "No problem. Please tell me again what you'd like to change about your booking."
                    response = make_response(twiml_response_with_gather(gather_text))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                else:
                    gather_text = "Please say 'yes' to confirm the changes or 'no' to try again."
                    response = make_response(twiml_response_with_gather(gather_text))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                    
            elif current_step == "confirm_cancel":
                if any(word in prompt for word in ["yes", "yeah", "yep", "confirm"]):
                    # Cancel the booking
                    cancelled_booking = bookings.pop(user_id, {})
                    user_sessions.pop(user_id, None)
                    
                    response = make_response(twiml_response("Your booking has been cancelled successfully. Thank you for calling Kiwi Cabs. Goodbye."))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                    
                elif any(word in prompt for word in ["no", "nah", "keep"]):
                    user_sessions.pop(user_id, None)
                    response = make_response(twiml_response("No problem. Your booking is still confirmed. Thank you for calling Kiwi Cabs. Goodbye."))
                    response.headers["Content-Type"] = "application/xml"
                    return response
                else:
                    gather_text = "Please say 'yes' to cancel your booking or 'no' to keep it."
                    response = make_response(twiml_response_with_gather(gather_text))
                    response.headers["Content-Type"] = "application/xml"
                    return response
        
        # Fallback for unrecognized flow
        response = make_response(twiml_response("I'm sorry, something went wrong. Please call back and try again. Goodbye."))
        response.headers["Content-Type"] = "application/xml"
        return response
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        response = make_response(twiml_response("Sorry, an error occurred. Please call back later. Goodbye."))
        response.headers["Content-Type"] = "application/xml"
        return response

if __name__ == "__main__":
    app.run(debug=True)