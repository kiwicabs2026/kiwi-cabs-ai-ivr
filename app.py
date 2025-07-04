import os
import base64
import json
import time
from datetime import datetime
import pytz
import requests
import psycopg2
from flask import Flask, request, jsonify

# Optional Google Speech imports
try:
    from google.cloud import speech
    from google.oauth2 import service_account
    GOOGLE_SPEECH_AVAILABLE = True
except ImportError:
    GOOGLE_SPEECH_AVAILABLE = False

# Environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY")
TAXICALLER_BASE_URL = os.getenv("TAXICALLER_BASE_URL", "https://api.taxicaller.net/api/v1")
DATABASE_URL = os.getenv("DATABASE_URL")

NZ_TZ = pytz.timezone("Pacific/Auckland")

app = Flask(__name__)

# Global cache for JWT tokens
TAXICALLER_JWT_CACHE = {"token": None, "expires_at": 0}

# ------------- Database helpers -------------
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ DB connection error: {e}")
        return None

# ------------- Google Speech recognition -------------
def init_google_speech():
    """Initialize Google Speech client with credentials"""
    if not GOOGLE_SPEECH_AVAILABLE:
        print("❌ Google Speech not available - using Twilio only")
        return None

    try:
        if GOOGLE_CREDENTIALS:
            creds_json = base64.b64decode(GOOGLE_CREDENTIALS).decode("utf-8")
            credentials = service_account.Credentials.from_service_account_info(
                json.loads(creds_json)
            )
            print("✅ Google Speech client initialized successfully")
            return speech.SpeechClient(credentials=credentials)
        print("⚠️ No Google credentials found")
        return None
    except Exception as e:
        print(f"❌ Failed to initialize Google Speech: {str(e)}")
        return None

# Initialize Google client if available
if GOOGLE_SPEECH_AVAILABLE:
    google_speech_client = init_google_speech()

def transcribe_with_google(audio_url):
    """Use Google Speech for better transcription"""
    if not GOOGLE_SPEECH_AVAILABLE or not google_speech_client:
        print("❌ Google Speech client not available")
        return None, 0

    try:
        print(f"🎤 Fetching audio from: {audio_url}")

        response = requests.get(audio_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        if response.status_code != 200:
            print(f"❌ Failed to download audio: {response.status_code}")
            return None, 0

        audio_content = response.content
        print(f"✅ Downloaded audio: {len(audio_content)} bytes")

        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,
            language_code="en-NZ",
            enable_automatic_punctuation=True,
            enable_word_confidence=True,
            speech_contexts=[
                speech.SpeechContext(
                    phrases=[
                        # Wellington Streets
                        "Willis Street", "Cuba Street", "Lambton Quay", "Courtenay Place",
                        "Taranaki Street", "Victoria Street", "Manners Street", "Dixon Street",
                        "Wakefield Street", "Cable Street", "Oriental Parade", "Kent Terrace",
                        "Hobart Street", "Molesworth Street", "The Terrace", "Featherston Street",
                        # Wellington Areas
                        "Wellington", "Lower Hutt", "Upper Hutt", "Porirua", "Petone",
                        "Island Bay", "Newtown", "Kilbirnie", "Miramar", "Karori", "Kelburn",
                        "Thorndon", "Te Aro", "Mount Victoria", "Oriental Bay",
                        # Major POIs & Landmarks
                        "Airport", "Wellington Airport", "Railway Station", "Train Station",
                        "Te Papa", "Te Papa Museum", "Westpac Stadium", "Sky Stadium",
                        "Wellington Zoo", "Cable Car", "Wellington Cable Car",
                        # Hospitals
                        "Hospital", "Wellington Hospital", "Hutt Hospital", "Bowen Hospital",
                        "Kenepuru Hospital", "Kapiti Hospital",
                        # Hotels
                        "James Cook Hotel", "InterContinental Wellington", "Bolton Hotel",
                        "Copthorne Hotel", "Travelodge Wellington", "YHA Wellington",
                        # Shopping Centers
                        "Westfield", "Westfield Queensgate", "Lambton Quay", "Cuba Mall",
                        "Johnsonville Mall", "Coastlands", "North City Shopping Centre",
                        # Entertainment & Attractions
                        "Weta Cave", "Weta Workshop", "Wellington Botanic Garden",
                        "Mount Victoria Lookout", "Carter Observatory", "City Gallery",
                        "National Library", "Parliament", "Parliament Buildings",
                        # Restaurants & Bars (popular ones)
                        "Logan Brown", "Charley Noble", "Molly Malone's", "Shed 5",
                        "Ortega Fish Shack", "Noble Rot Wine Bar", "Havana Coffee Works",
                        # Universities & Schools
                        "Victoria University", "Massey University", "Whitireia",
                        # Transport Hubs
                        "Wellington Station", "Waterloo Station", "Petone Station",
                        "Lower Hutt Station", "Upper Hutt Station", "Johnsonville Station"
                    ],
                    boost=20.0,
                )
            ],
            max_alternatives=3,
            model="phone_call",
            use_enhanced=True,
        )

        print("🔄 Sending to Google Speech API...")
        response = google_speech_client.recognize(config=config, audio=audio)

        if response.results:
            best_result = response.results[0].alternatives[0]
            confidence = best_result.confidence
            transcript = best_result.transcript

            print(
                f"✅ GOOGLE SPEECH RESULT: {transcript} (confidence: {confidence:.2f})"
            )
            return transcript, confidence
        else:
            print("❌ No speech detected by Google")
            return None, 0

    except Exception as e:
        print(f"❌ Google Speech Error: {str(e)}")
        return None, 0

# ------------- TaxiCaller JWT -------------
def get_taxicaller_jwt():
    print("🚀 Starting get_taxicaller_jwt()")
    if (
        TAXICALLER_JWT_CACHE["token"]
        and time.time() < TAXICALLER_JWT_CACHE["expires_at"]
    ):
        print("📌 Using cached JWT token")
        return TAXICALLER_JWT_CACHE["token"]

    if not TAXICALLER_API_KEY:
        print("❌ No TaxiCaller API key configured - skipping JWT")
        return None

    try:
        jwt_endpoints = [
            "https://api-rc.taxicaller.net/api/v1/jwt/for-key",
        ]
        params = {"key": TAXICALLER_API_KEY, "sub": "*", "ttl": "900"}

        for jwt_url in jwt_endpoints:
            print(f"🔑 Trying JWT endpoint: {jwt_url}")
            try:
                response = requests.get(jwt_url, params=params, timeout=5)
                print(f"🌐 Status Code: {response.status_code}")
                print(f"📥 Raw Response: {response.text}")

                if response.status_code == 200:
                    jwt_token = response.text.strip()
                    TAXICALLER_JWT_CACHE["token"] = jwt_token
                    TAXICALLER_JWT_CACHE["expires_at"] = time.time() + 840
                    print(f"✅ JWT token generated successfully from {jwt_url}")
                    return jwt_token
                else:
                    print(f"❌ Failed JWT endpoint {jwt_url}: {response.status_code}")
            except Exception as e:
                print(f"❌ JWT endpoint {jwt_url} error: {str(e)}")
                continue

        print("❌ All JWT endpoints failed")
        return None

    except Exception as e:
        print(f"❌ Error generating JWT: {str(e)}")
        return None

# ✅ Call it
get_taxicaller_jwt()

# ------------- Conversation and Booking DB helpers -------------

def save_conversation(phone_number, message, role="user"):
    """Save conversation to the database"""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO conversations (phone_number, message, role)
                VALUES (%s, %s, %s)
                """,
                (phone_number, message, role),
            )
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print(f"❌ Error saving conversation: {e}")

def get_conversation_history(phone_number, limit=10):
    """Get recent conversation history for phone"""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT message, role, timestamp
                FROM conversations
                WHERE phone_number = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (phone_number, limit),
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows[::-1]  # Oldest first
    except Exception as e:
        print(f"❌ Error fetching conversation: {e}")
    return []

def save_booking(
    customer_phone,
    customer_name,
    pickup_location,
    dropoff_location,
    booking_reference,
    scheduled_time=None,
    status="pending",
    raw_speech=None,
    pickup_date=None,
    pickup_time=None,
    created_via="ai_ivr",
):
    """Save a booking to the database"""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO bookings
                (customer_phone, customer_name, pickup_location, dropoff_location, booking_reference, scheduled_time, status, raw_speech, pickup_date, pickup_time, created_via)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    customer_phone,
                    customer_name,
                    pickup_location,
                    dropoff_location,
                    booking_reference,
                    scheduled_time,
                    status,
                    raw_speech,
                    pickup_date,
                    pickup_time,
                    created_via,
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            print("✅ Booking saved to DB")
            return True
    except Exception as e:
        print(f"❌ Error saving booking: {e}")
    return False

def get_latest_booking(phone_number):
    """Get the latest booking for a phone number"""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT *
                FROM bookings
                WHERE customer_phone = %s
                ORDER BY booking_time DESC
                LIMIT 1
                """,
                (phone_number,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row
    except Exception as e:
        print(f"❌ Error fetching latest booking: {e}")
    return None

def update_booking_status(booking_id, status):
    """Update booking status in DB"""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE bookings SET status = %s WHERE id = %s", (status, booking_id)
            )
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print(f"❌ Error updating booking status: {e}")

def get_customer(phone_number):
    """Get customer by phone"""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM customers WHERE phone_number = %s", (phone_number,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row
    except Exception as e:
        print(f"❌ Error fetching customer: {e}")
    return None

def save_customer(phone_number, name=None):
    """Save new customer if doesn't exist"""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO customers (phone_number, name) VALUES (%s, %s) ON CONFLICT (phone_number) DO NOTHING",
                (phone_number, name),
            )
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print(f"❌ Error saving customer: {e}")

def update_customer_name(phone_number, name):
    """Update customer name in DB"""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE customers SET name = %s WHERE phone_number = %s",
                (name, phone_number),
            )
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print(f"❌ Error updating customer name: {e}")

# ------------- OpenAI intent helpers -------------
def get_openai_completion(prompt, temperature=0.4, max_tokens=256, stop=None):
    """Call OpenAI API with robust error handling"""
    if not OPENAI_API_KEY:
        print("❌ No OpenAI API Key configured")
        return None

    url = "https://api.openai.com/v1/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    data = {
        "model": "text-davinci-003",
        "prompt": prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if stop:
        data["stop"] = stop

    try:
        response = requests.post(url, headers=headers, json=data, timeout=12)
        if response.status_code == 200:
            result = response.json()
            text = result["choices"][0]["text"].strip()
            print(f"🤖 OpenAI returned: {text}")
            return text
        else:
            print(f"❌ OpenAI Error: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ OpenAI Exception: {e}")
    return None

def extract_modification_intent(user_text, booking_data):
    """
    Use OpenAI to parse the user's request and extract intent in JSON.
    Always returns a dict with at least an "intent" key.
    """
    # Compose prompt
    prompt = (
        f"""The user has requested to change their taxi booking. Their request was: "{user_text}".\n"""
        f"""The current booking is:\n"""
        f"""Pickup Address: {booking_data.get('pickup_location')}\n"""
        f"""Dropoff Address: {booking_data.get('dropoff_location') or 'Unknown'}\n"""
        f"""Pickup Time: {booking_data.get('pickup_time') or 'Unknown'} / Date: {booking_data.get('pickup_date') or 'Unknown'}\n"""
        f"""Please extract the user's MODIFICATION INTENT as a JSON object with only these keys:\n"""
        f"""- intent: one of ["change_time", "change_pickup", "change_destination", "cancel_booking", "no_change"]\n"""
        f"""- new_time: (string) only if intent is 'change_time' (otherwise null)\n"""
        f"""- new_pickup: (string) only if intent is 'change_pickup' (otherwise null)\n"""
        f"""- new_destination: (string) only if intent is 'change_destination' (otherwise null)\n"""
        f"""- reason: (string) (e.g. if cancelling, why; otherwise, short summary)\n"""
        f"""Example output:\n"""
        f"""{{"intent": "change_time", "new_time": "10:30am", "new_pickup": null, "new_destination": null, "reason": "User wants to change pickup time"}}\n"""
        f"""Only output valid JSON. If the intent is unclear, set intent to "no_change" and reason to "Could not understand the request".\n"""
    )

    ai_response = get_openai_completion(prompt)
    fallback = {"intent": "no_change", "new_time": None, "new_pickup": None, "new_destination": None, "reason": "Could not understand the request"}

    if not ai_response:
        return fallback

    try:
        # Try to extract JSON from the response robustly
        json_start = ai_response.find("{")
        json_end = ai_response.rfind("}") + 1
        ai_json = ai_response[json_start:json_end]
        intent_data = json.loads(ai_json)
        print(f"✅ Parsed AI intent: {intent_data}")
        # Normalize None/nulls
        for k in ["new_time", "new_pickup", "new_destination"]:
            if k in intent_data and intent_data[k] == "":
                intent_data[k] = None
        return intent_data
    except Exception as e:
        print(f"❌ AI intent parse error: {e} - Got: {ai_response}")
        return fallback

# ------------- TaxiCaller API booking actions -------------
def get_taxicaller_booking_status(booking_ref):
    """Query TaxiCaller for live booking status"""
    jwt = get_taxicaller_jwt()
    if not jwt:
        return None
    try:
        url = f"{TAXICALLER_BASE_URL}/booker/order/{booking_ref}"
        headers = {"Authorization": f"Bearer {jwt}"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ TaxiCaller booking status: {data.get('status')}")
            return data
        else:
            print(f"❌ TaxiCaller booking status failed: {resp.status_code}")
            return None
    except Exception as e:
        print(f"❌ TaxiCaller status error: {e}")
        return None

def cancel_taxicaller_booking(booking_ref):
    """Cancel booking via TaxiCaller API"""
    jwt = get_taxicaller_jwt()
    if not jwt:
        return False, "JWT error"
    try:
        url = f"{TAXICALLER_BASE_URL}/booker/order/{booking_ref}/cancel"
        headers = {"Authorization": f"Bearer {jwt}"}
        resp = requests.post(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            print(f"✅ Booking {booking_ref} cancelled in TaxiCaller")
            return True, None
        else:
            print(f"❌ Cancel failed: {resp.status_code} {resp.text}")
            return False, resp.text
    except Exception as e:
        print(f"❌ Cancel API exception: {e}")
        return False, str(e)

def update_taxicaller_booking_time(booking_ref, new_time):
    """Update booking time in TaxiCaller"""
    jwt = get_taxicaller_jwt()
    if not jwt:
        return False, "JWT error"
    try:
        url = f"{TAXICALLER_BASE_URL}/booker/order/{booking_ref}/update"
        headers = {"Authorization": f"Bearer {jwt}"}
        payload = {"pickupTime": new_time}
        resp = requests.post(url, headers=headers, json=payload, timeout=8)
        if resp.status_code == 200:
            print(f"✅ Booking time updated in TaxiCaller: {new_time}")
            return True, None
        else:
            print(f"❌ Update time failed: {resp.status_code} {resp.text}")
            return False, resp.text
    except Exception as e:
        print(f"❌ Update time API exception: {e}")
        return False, str(e)

def update_taxicaller_booking_address(booking_ref, field, new_address):
    """Update pickup or dropoff address in TaxiCaller"""
    jwt = get_taxicaller_jwt()
    if not jwt:
        return False, "JWT error"
    try:
        url = f"{TAXICALLER_BASE_URL}/booker/order/{booking_ref}/update"
        headers = {"Authorization": f"Bearer {jwt}"}
        payload = {field: new_address}
        resp = requests.post(url, headers=headers, json=payload, timeout=8)
        if resp.status_code == 200:
            print(f"✅ Booking {field} updated in TaxiCaller: {new_address}")
            return True, None
        else:
            print(f"❌ Update {field} failed: {resp.status_code} {resp.text}")
            return False, resp.text
    except Exception as e:
        print(f"❌ Update address API exception: {e}")
        return False, str(e)

# -------- Flask endpoints for booking modification --------

@app.route("/process_modification_smart", methods=["POST"])
def process_modification_smart():
    """
    Process a booking modification request using AI to extract intent.
    Expects JSON:
      {
        "phone_number": "...",
        "modification_text": "...",   # user request in natural language
      }
    """
    data = request.get_json(force=True)
    phone_number = data.get("phone_number")
    mod_text = data.get("modification_text")
    print(f"🔄 /process_modification_smart: {phone_number}, text: {mod_text}")

    if not phone_number or not mod_text:
        return jsonify({"error": "Missing phone_number or modification_text"}), 400

    # Get latest booking
    booking = get_latest_booking(phone_number)
    if not booking:
        return jsonify({"error": "No existing booking found for this number"}), 404

    # Use OpenAI to extract modification intent
    intent = extract_modification_intent(mod_text, booking)
    print(f"🧠 AI extracted intent: {intent}")

    # Handle intent
    action = intent.get("intent")
    response = {"result": "no_change", "message": "No changes detected or understood"}

    try:
        if action == "cancel_booking":
            # Cancel in TaxiCaller
            ref = booking.get("booking_reference")
            ok, err = cancel_taxicaller_booking(ref)
            if ok:
                update_booking_status(booking["id"], "cancelled")
                response = {
                    "result": "cancelled",
                    "message": "Your booking has been cancelled.",
                }
            else:
                response = {
                    "result": "cancel_failed",
                    "message": f"Could not cancel booking: {err or 'Unknown error'}",
                }

        elif action == "change_time":
            # Change time in TaxiCaller
            new_time = intent.get("new_time")
            ref = booking.get("booking_reference")
            # Try to parse/convert new_time to correct format if needed
            if new_time:
                # Expecting a string like "10:30am"
                try:
                    # If the pickup_date is set, join with new_time and parse
                    pickup_date = booking.get("pickup_date") or datetime.now(NZ_TZ).strftime("%Y-%m-%d")
                    dt_str = f"{pickup_date} {new_time}"
                    dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %I:%M%p")
                    # Convert to UTC ISO8601 (as TaxiCaller expects)
                    dt_utc = dt_obj.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    ok, err = update_taxicaller_booking_time(ref, dt_utc)
                    if ok:
                        response = {
                            "result": "time_changed",
                            "message": f"Pickup time changed to {new_time}",
                        }
                        # Update locally as well
                        update_booking_status(booking["id"], "updated")
                    else:
                        response = {
                            "result": "time_change_failed",
                            "message": f"Could not change time: {err or 'Unknown error'}",
                        }
                except Exception as e:
                    print(f"❌ Error parsing new_time: {e}")
                    response = {
                        "result": "time_change_failed",
                        "message": "Could not understand the new time format.",
                    }
            else:
                response = {
                    "result": "time_change_failed",
                    "message": "No new time provided.",
                }

        elif action == "change_pickup":
            new_pickup = intent.get("new_pickup")
            ref = booking.get("booking_reference")
            if new_pickup:
                # Validate address
                clean_address = validate_and_format_address(new_pickup, "pickup")
                ok, err = update_taxicaller_booking_address(ref, "pickupAddress", clean_address)
                if ok:
                    response = {
                        "result": "pickup_changed",
                        "message": f"Pickup address changed to {clean_address}",
                    }
                    update_booking_status(booking["id"], "updated")
                else:
                    response = {
                        "result": "pickup_change_failed",
                        "message": f"Could not change pickup: {err or 'Unknown error'}",
                    }
            else:
                response = {
                    "result": "pickup_change_failed",
                    "message": "No new pickup address provided.",
                }

        elif action == "change_destination":
            new_dest = intent.get("new_destination")
            ref = booking.get("booking_reference")
            if new_dest:
                clean_address = validate_and_format_address(new_dest, "destination")
                ok, err = update_taxicaller_booking_address(ref, "dropoffAddress", clean_address)
                if ok:
                    response = {
                        "result": "destination_changed",
                        "message": f"Destination changed to {clean_address}",
                    }
                    update_booking_status(booking["id"], "updated")
                else:
                    response = {
                        "result": "destination_change_failed",
                        "message": f"Could not change destination: {err or 'Unknown error'}",
                    }
            else:
                response = {
                    "result": "destination_change_failed",
                    "message": "No new destination provided.",
                }

        elif action == "no_change":
            response = {
                "result": "no_change",
                "message": "Sorry, I couldn't understand your request.",
            }

        else:
            response = {
                "result": "unsupported",
                "message": f"Intent '{action}' is not supported.",
            }

        return jsonify(response), 200

    except Exception as exc:
        print(f"❌ process_modification_smart error: {exc}")
        return jsonify({"error": "Internal error", "details": str(exc)}), 500

@app.route("/booking_status", methods=["POST"])
def booking_status():
    """
    Check booking status for a user's latest booking.
    Expects JSON: { "phone_number": "..." }
    """
    data = request.get_json(force=True)
    phone_number = data.get("phone_number")
    if not phone_number:
        return jsonify({"error": "Missing phone_number"}), 400

    booking = get_latest_booking(phone_number)
    if not booking:
        return jsonify({"error": "No booking found"}), 404

    ref = booking.get("booking_reference")
    status_data = get_taxicaller_booking_status(ref)
    if not status_data:
        return jsonify({"error": "Could not fetch live status"}), 503

    return jsonify({
        "booking_reference": ref,
        "status": status_data.get("status"),
        "eta": status_data.get("eta"),
        "vehicle": status_data.get("vehicle"),
        "driver": status_data.get("driver"),
        "raw": status_data
    }), 200

@app.route("/cancel_booking", methods=["POST"])
def cancel_booking():
    """
    Cancel user's latest booking.
    Expects JSON: { "phone_number": "..." }
    """
    data = request.get_json(force=True)
    phone_number = data.get("phone_number")
    if not phone_number:
        return jsonify({"error": "Missing phone_number"}), 400

    booking = get_latest_booking(phone_number)
    if not booking:
        return jsonify({"error": "No booking found"}), 404

    ref = booking.get("booking_reference")
    ok, err = cancel_taxicaller_booking(ref)
    if ok:
        update_booking_status(booking["id"], "cancelled")
        return jsonify({"result": "cancelled", "message": "Booking cancelled."}), 200
    else:
        return jsonify({"result": "failed", "error": err or "Unknown error"}), 500

@app.route("/conversation_history", methods=["POST"])
def conversation_history():
    """
    Get recent conversation history for a phone number.
    Expects JSON: { "phone_number": "..." }
    """
    data = request.get_json(force=True)
    phone_number = data.get("phone_number")
    limit = int(data.get("limit", 10))

    if not phone_number:
        return jsonify({"error": "Missing phone_number"}), 400

    history = get_conversation_history(phone_number, limit=limit)
    return jsonify({"history": history}), 200

@app.route("/healthz")
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "ok", "time": datetime.now(NZ_TZ).isoformat()}), 200

if __name__ == "__main__":
    # For debugging locally. In production, use gunicorn or similar.
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))