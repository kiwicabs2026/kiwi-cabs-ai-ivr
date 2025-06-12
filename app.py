import os
import re
import json
from flask import Flask, request, Response
import openai
from twilio.twiml.voice_response import VoiceResponse, Gather

app = Flask(__name__)

# Load OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OpenAI API key is not set in environment variable OPENAI_API_KEY")

# def extract_booking_details(text):
#     prompt = f"""
# Extract the following details from the text:

# - Name  
# - Pickup location  
# - Drop-off location  
# - Date and time  

# Return the result as a JSON object with keys: name, pickup, dropoff, datetime.

# Text: "{text}"
# """

#     response = openai.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant that extracts structured data."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0,
#         max_tokens=150
#     )

#     extracted_text = response.choices[0].message.content.strip()
#     # Remove markdown code blocks if present
#     cleaned = re.sub(r"```json|```", "", extracted_text).strip()

#     try:
#         data = json.loads(cleaned)
#         return data
#     except Exception as e:
#         print("Error parsing JSON:", e)
#         print("Raw response:", extracted_text)
#         return None
def extract_booking_details(text):
    prompt = f"""
Extract the following details from the text:

- Name  
- Pickup location  
- Drop-off location  
- Date and time  

Return the result as a JSON object with keys: name, pickup, dropoff, datetime.

Text: "{text}"
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts structured data."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=150
    )

    extracted_text = response['choices'][0]['message']['content'].strip()
    cleaned = re.sub(r"```json|```", "", extracted_text).strip()

    try:
        data = json.loads(cleaned)
        return data
    except Exception as e:
        print("Error parsing JSON:", e)
        print("Raw response:", extracted_text)
        return None

@app.route('/ask', methods=['POST'])
def ask():
    transcription = request.form.get('SpeechResult', '')
    details = extract_booking_details(transcription)

    response = VoiceResponse()

    if not details:
        response.say("Sorry, we could not understand your request. Please try again.")
        response.hangup()
        return Response(str(response), mimetype='application/xml')

    name = details.get('name', 'Guest')
    pickup = details.get('pickup', 'Unknown')
    dropoff = details.get('dropoff', 'Unknown')
    datetime_text = details.get('datetime', 'Unknown')

    # Redirect to confirmation with extracted details as query params
    response.redirect(f"/confirm_booking?name={name}&pickup={pickup}&dropoff={dropoff}&datetime={datetime_text}")
    return Response(str(response), mimetype='application/xml')

@app.route('/confirm_booking', methods=['GET', 'POST'])
def confirm_booking():
    name = request.args.get('name', 'Guest')
    pickup = request.args.get('pickup', 'Unknown')
    dropoff = request.args.get('dropoff', 'Unknown')
    datetime_text = request.args.get('datetime', 'Unknown')

    response = VoiceResponse()
    gather = Gather(num_digits=1, action='/handle_confirmation', method='POST')
    gather.say(f"Thanks {name}. You’ve requested a taxi from {pickup} to {dropoff} at {datetime_text}. "
               "If that’s correct, press 1. To cancel, press 2.")
    response.append(gather)

    response.say("We didn't get your response. Goodbye.")
    response.hangup()
    return Response(str(response), mimetype='application/xml')

@app.route('/handle_confirmation', methods=['POST'])
def handle_confirmation():
    digit = request.form.get('Digits')
    response = VoiceResponse()

    if digit == '1':
        response.say("Your taxi booking is confirmed. Thank you! Goodbye.")
        # TODO: Add database save or SMS confirmation here
    elif digit == '2':
        response.say("Your booking has been canceled. Goodbye.")
    else:
        response.say("Invalid input. Goodbye.")

    response.hangup()
    return Response(str(response), mimetype='application/xml')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
