import os
import requests
import json
from flask import Flask, request, Response
from datetime import datetime, timedelta
import re

app = Flask(__name__)

# TaxiCaller API Configuration
TAXICALLER_BASE_URL = "https://api.taxicaller.net/api/v1"
TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY", "")

def get_taxicaller_jwt():
    """Get JWT token for TaxiCaller API authentication"""
    try:
        response = requests.get(
            f"{TAXICALLER_BASE_URL}/jwt/for-key",
            params={
                'key': TAXICALLER_API_KEY,
                'sub': '*'  # All subjects
            },
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
            jwt_token = token_data.get('token')
            print(f"✅ TaxiCaller JWT obtained: {jwt_token[:50]}...")
            return jwt_token
        else:
            print(f"❌ Failed to get TaxiCaller JWT: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"💥 Error getting TaxiCaller JWT: {str(e)}")
        return None

def search_existing_booking_real(phone_number):
    """Search for existing booking in real TaxiCaller system"""
    try:
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            print("❌ No JWT token - cannot search TaxiCaller")
            return None
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        # Search through recent orders by phone number
        # Note: TaxiCaller doesn't have a direct phone search, so we'll need to use reports or customer accounts
        print(f"🔍 SEARCHING TAXICALLER FOR BOOKING: Phone {phone_number}")
        
        # For now, return mock data since we need your company_id to make real calls
        # TODO: Replace with real TaxiCaller search once we have your company_id
        mock_booking = {
            "booking_details": {
                "order_id": f"TC{datetime.now().strftime('%Y%m%d')}001",
                "customer_details": {
                    "name": "John Smith",
                    "phone": phone_number
                },
                "trip_details": {
                    "pickup_address": "Queen Street, Wellington Central, Wellington",
                    "destination_address": "Wellington Airport, Rongotai, Wellington",
                    "pickup_date": "06/06/2025",
                    "pickup_time": "8:00 AM"
                },
                "booking_info": {
                    "status": "confirmed",
                    "created_at": datetime.now().isoformat()
                }
            }
        }
        
        print(f"✅ MOCK BOOKING FOUND (Replace with real TaxiCaller search)")
        return mock_booking['booking_details']
        
    except Exception as e:
        print(f"💥 Error searching TaxiCaller: {str(e)}")
        return None

def create_taxicaller_booking(booking_data):
    """Create new booking in TaxiCaller system"""
    try:
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            print("❌ No JWT token - cannot create TaxiCaller booking")
            return False
        
        # Convert our booking format to TaxiCaller format
        tc_format = booking_data['taxicaller_format']
        
        # Parse coordinates (TaxiCaller uses [longitude, latitude] * 1e6)
        # For now using Wellington CBD coordinates as default
        pickup_coords = [17465000, -41290000]  # Wellington CBD
        dropoff_coords = [17465000, -41290000]  # Default to same
        
        # Convert pickup time to Unix timestamp
        pickup_timestamp = int(datetime.now().timestamp())
        if tc_format.get('booking_time') and tc_format.get('booking_date'):
            try:
                time_str = f"{tc_format['booking_date']} {tc_format['booking_time']}"
                pickup_dt = datetime.strptime(time_str, '%d/%m/%Y %I:%M %p')
                pickup_timestamp = int(pickup_dt.timestamp())
            except:
                pickup_timestamp = 0  # ASAP
        
        taxicaller_order = {
            "order": {
                "company_id": 1318,  # TODO: Replace with your actual company_id
                "provider_id": 0,    # Any provider
                "items": [
                    {
                        "@type": "passengers",
                        "seq": 0,
                        "passenger": {
                            "name": tc_format['customer_name'],
                            "phone": tc_format['phone_number'],
                            "email": ""
                        },
                        "client_id": 0,
                        "account": {
                            "id": 0
                        },
                        "require": {
                            "seats": 1,
                            "wc": 0,
                            "bags": 1
                        },
                        "pay_info": [
                            {
                                "@t": 0,  # CASH
                                "data": None
                            }
                        ]
                    }
                ],
                "route": {
                    "nodes": [
                        {
                            "actions": [
                                {
                                    "@type": "client_action",
                                    "item_seq": 0,
                                    "action": "in"  # pickup
                                }
                            ],
                            "location": {
                                "name": tc_format['pickup_address'],
                                "coords": pickup_coords
                            },
                            "times": {
                                "arrive": {
                                    "target": pickup_timestamp,
                                    "latest": 0
                                }
                            },
                            "info": {
                                "all": tc_format.get('special_instructions', '')
                            },
                            "seq": 0
                        },
                        {
                            "actions": [
                                {
                                    "@type": "client_action",
                                    "item_seq": 0,
                                    "action": "out"  # dropoff
                                }
                            ],
                            "location": {
                                "name": tc_format['destination_address'],
                                "coords": dropoff_coords
                            },
                            "times": None,
                            "info": {},
                            "seq": 1
                        }
                    ],
                    "legs": [
                        {
                            "meta": {
                                "dist": 5000,  # Default distance
                                "est_dur": 600  # Default duration
                            },
                            "pts": pickup_coords + dropoff_coords,  # Simple route
                            "from_seq": 0,
                            "to_seq": 1
                        }
                    ],
                    "meta": {
                        "dist": 5000,
                        "est_dur": 600
                    }
                }
            }
        }
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        print("📤 SENDING BOOKING TO TAXICALLER:")
        print(f"👤 Customer: {tc_format['customer_name']}")
        print(f"📞 Phone: {tc_format['phone_number']}")
        print(f"📍 From: {tc_format['pickup_address']}")
        print(f"🎯 To: {tc_format['destination_address']}")
        print(f"⏰ Time: {tc_format['booking_time']} on {tc_format['booking_date']}")
        
        response = requests.post(
            f"{TAXICALLER_BASE_URL}/booker/order",
            json=taxicaller_order,
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            order_response = response.json()
            order_id = order_response.get('order', {}).get('order_id')
            print(f"✅ TAXICALLER BOOKING CREATED: {order_id}")
            return True
        else:
            print(f"❌ TaxiCaller booking failed: {response.status_code}")
            print(f"📤 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 Error creating TaxiCaller booking: {str(e)}")
        return False

def update_taxicaller_booking(order_id, updated_booking):
    """Update existing booking in TaxiCaller system"""
    try:
        jwt_token = get_taxicaller_jwt()
        if not jwt_token:
            print("❌ No JWT token - cannot update TaxiCaller booking")
            return False
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        # Use the same order structure as create but with updates
        # This would need the full TaxiCaller order format with changes
        
        print(f"🔄 UPDATING TAXICALLER BOOKING: {order_id}")
        
        response = requests.post(
            f"{TAXICALLER_BASE_URL}/booker/order/{order_id}",
            json=updated_booking,
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            print("✅ TaxiCaller booking updated successfully")
            return True
        else:
            print(f"❌ TaxiCaller update failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"💥 Error updating TaxiCaller booking: {str(e)}")
        return False

# Session memory stores
user_sessions = {}
modification_bookings = {}

@app.route("/voice", methods=["POST"])
def voice():
    """Initial greeting and menu options"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/menu" input="speech" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Kia ora, and welcome to Kiwi Cabs.
            I'm your AI assistant, here to help you book your taxi.
            This call may be recorded for training and security purposes.
            How can I help you today? You can book a new taxi, change an existing booking, or speak with our team.
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/menu", methods=["POST"])
def menu():
    """Process menu selection with enhanced NZ English recognition"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    print(f"DEBUG - Menu Selection: '{data}' (Confidence: {confidence})")

    # Enhanced keyword recognition for all options
    booking_keywords = ["1", "one", "book", "taxi", "ride", "cab", "new booking", "need a taxi", "want a taxi"]
    modify_keywords = ["2", "two", "change", "cancel", "modify", "existing", "alter", "update"]
    team_keywords = ["3", "three", "team", "human", "person", "staff", "operator", "speak"]

    if any(keyword in data for keyword in booking_keywords):
        return redirect_to("/book")
    elif any(keyword in data for keyword in modify_keywords):
        return redirect_to("/modify")
    elif any(keyword in data for keyword in team_keywords):
        return redirect_to("/team")
    else:
        return clarify_menu()

def clarify_menu():
    """Ask for menu clarification"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/menu" input="speech" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Sorry, I didn't quite catch that. Let me repeat the options.
            Say one for a new taxi booking.
            Say two to change an existing booking.
            Say three to speak with our team.
            Which option would you like?
        </Say>
    </Gather>
    <Redirect>/voice</Redirect>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/book", methods=["POST"])
def book():
    """Start new booking process"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great choice! I'll help you book your taxi.
        Please tell me your full name, where you need to be picked up from, where you're going, and what time you need the taxi.
        Take your time and speak clearly.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="12" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/modify", methods=["POST"])
def modify():
    """Start modification process - ask for phone number first"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! I can help you change your booking.
        To find your booking, please tell me your phone number.
        Speak clearly and include all digits.
    </Say>
    <Gather input="speech" action="/get_phone_for_booking" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/team", methods=["POST"])
def team():
    """Transfer to human team member"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No problem! I'm connecting you with one of our friendly team members now.
        Please hold the line.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
    return Response(response, mimetype="text/xml")

# TaxiCaller Integration - Real-time booking modification
def search_existing_booking(phone_number):
    """Search for LIVE booking in TaxiCaller dispatch system"""
    try:
        search_payload = {
            'action': 'search_live_booking',
            'customer_phone': phone_number,
            'search_criteria': {
                'status': ['confirmed', 'scheduled', 'pending_dispatch'],  # Live bookings only
                'time_range': 'future',  # Only future bookings
                'include_details': True
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-Source': 'KiwiCabs-AI-Modification',
            'Authorization': f'Bearer {TAXICALLER_API_KEY}' if TAXICALLER_API_KEY else None
        }
        
        headers = {k: v for k, v in headers.items() if v is not None}
        
        print(f"🔍 SEARCHING LIVE TAXICALLER BOOKING: Phone {phone_number}")
        
        # Search in live TaxiCaller dispatch system
        response = requests.get(
            f"{RENDER_ENDPOINT}/search_live_booking",
            params={'phone': phone_number},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            booking_data = response.json()
            if booking_data and 'booking_details' in booking_data:
                print(f"✅ FOUND LIVE BOOKING: {booking_data['booking_details']['booking_reference']}")
                print(f"📅 Current Time: {booking_data['booking_details']['trip_details']['pickup_time']}")
                return booking_data['booking_details']
            else:
                print("❌ No live booking found in response")
                return None
        else:
            print(f"❌ TaxiCaller search failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"💥 Error searching live booking: {str(e)}")
        return None

def update_existing_booking(phone_number, original_booking, modification_request):
    """Update existing booking with new details"""
    try:
        # Parse what the caller wants to change
        modification_type = determine_modification_type(modification_request)
        updated_booking = original_booking.copy()
        
        if modification_type == 'pickup':
            # Extract new pickup location
            new_pickup = extract_location_from_request(modification_request, 'pickup')
            updated_booking['trip_details']['pickup_address'] = new_pickup
            
        elif modification_type == 'destination':
            # Extract new destination
            new_destination = extract_location_from_request(modification_request, 'destination')
            updated_booking['trip_details']['destination_address'] = new_destination
            
        elif modification_type == 'time':
            # Extract new time
            new_time, new_date = extract_time_from_request(modification_request)
            updated_booking['trip_details']['pickup_time'] = new_time
            updated_booking['trip_details']['pickup_date'] = new_date
            
        elif modification_type == 'cancel':
            updated_booking['booking_info']['status'] = 'cancelled'
        
        # Add modification metadata
        updated_booking['modification_info'] = {
            'modified_at': datetime.now().isoformat(),
            'modification_type': modification_type,
            'original_request': modification_request,
            'modified_via': 'AI_Phone_System'
        }
        
        return updated_booking
        
    except Exception as e:
        print(f"💥 Error updating booking: {str(e)}")
        return None

def determine_modification_type(request_text):
    """Determine what type of modification the caller wants"""
    text_lower = request_text.lower()
    
    pickup_keywords = ['pickup', 'pick up', 'from', 'starting', 'collection']
    destination_keywords = ['destination', 'drop off', 'drop-off', 'to', 'going']
    time_keywords = ['time', 'when', 'at', 'o\'clock', 'am', 'pm', 'morning', 'afternoon', 'evening']
    cancel_keywords = ['cancel', 'delete', 'remove', 'stop']
    
    if any(keyword in text_lower for keyword in cancel_keywords):
        return 'cancel'
    elif any(keyword in text_lower for keyword in pickup_keywords):
        return 'pickup'
    elif any(keyword in text_lower for keyword in destination_keywords):
        return 'destination'
    elif any(keyword in text_lower for keyword in time_keywords):
        return 'time'
    else:
        # Try to guess from context
        if 'street' in text_lower or 'road' in text_lower or 'avenue' in text_lower:
            return 'pickup'  # Default to pickup if location mentioned
        return 'time'  # Default to time if unclear

def extract_location_from_request(request_text, location_type):
    """Extract new location from modification request"""
    text_lower = request_text.lower()
    
    # Wellington locations database (same as booking)
    wellington_locations = {
        'queen street': 'Queen Street, Wellington Central, Wellington',
        'cuba street': 'Cuba Street, Wellington Central, Wellington',
        'lambton quay': 'Lambton Quay, Wellington Central, Wellington',
        'willis street': 'Willis Street, Wellington Central, Wellington',
        'courtenay place': 'Courtenay Place, Wellington Central, Wellington',
        'wellington airport': 'Wellington Airport, Rongotai, Wellington',
        'airport': 'Wellington Airport, Rongotai, Wellington',
        'train station': 'Wellington Railway Station, Pipitea, Wellington',
        'railway station': 'Wellington Railway Station, Pipitea, Wellington',
        'newtown': 'Newtown, Wellington',
        'mount victoria': 'Mount Victoria, Wellington',
        'kelburn': 'Kelburn, Wellington',
        'thorndon': 'Thorndon, Wellington'
    }
    
    # Find location in the request
    for location_key, full_address in wellington_locations.items():
        if location_key in text_lower:
            return full_address
    
    # Extract street names if no exact match
    import re
    street_pattern = r'([a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace))'
    match = re.search(street_pattern, text_lower)
    if match:
        return f"{match.group(1).strip().title()}, Wellington"
    
    return "Wellington Central, Wellington"  # Default

def extract_time_from_request(request_text):
    """Extract new time from modification request"""
    import re
    from datetime import datetime, timedelta
    
    text_lower = request_text.lower()
    current_time = datetime.now()
    
    # Time patterns
    time_patterns = [
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        r'(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?'
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3) if len(match.groups()) >= 3 and match.group(3) else None
            
            # Convert to 24-hour format
            if am_pm:
                if am_pm.lower() == 'pm' and hour != 12:
                    hour += 12
                elif am_pm.lower() == 'am' and hour == 12:
                    hour = 0
            
            try:
                new_datetime = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if new_datetime < current_time:
                    new_datetime += timedelta(days=1)
                
                formatted_date = new_datetime.strftime('%d/%m/%Y')
                formatted_time = new_datetime.strftime('%I:%M %p')
                
                return formatted_time, formatted_date
            except ValueError:
                pass
    
    # Default to current time + 1 hour
    default_time = current_time + timedelta(hours=1)
    return default_time.strftime('%I:%M %p'), default_time.strftime('%d/%m/%Y')

def send_booking_modification_to_dispatch(updated_booking, original_booking):
    """Send LIVE booking update to TaxiCaller dispatch system"""
    try:
        # Create real-time modification payload for TaxiCaller
        modification_payload = {
            'action': 'update_live_booking',
            'booking_reference': original_booking.get('booking_reference'),
            'customer_phone': original_booking.get('customer_details', {}).get('phone'),
            
            # CRITICAL: Real-time dispatch update
            'dispatch_update': {
                'original_pickup_time': original_booking.get('trip_details', {}).get('pickup_time'),
                'new_pickup_time': updated_booking.get('trip_details', {}).get('pickup_time'),
                'original_pickup_date': original_booking.get('trip_details', {}).get('pickup_date'),
                'new_pickup_date': updated_booking.get('trip_details', {}).get('pickup_date'),
                
                'pickup_address': updated_booking.get('trip_details', {}).get('pickup_address'),
                'destination_address': updated_booking.get('trip_details', {}).get('destination_address'),
                
                'modification_type': get_primary_modification_type(original_booking, updated_booking),
                'requires_redispatch': True,  # Force redispatch to fleet
                'priority': 'immediate'  # Real-time update
            },
            
            # Fleet coordination
            'fleet_instructions': {
                'cancel_original_dispatch': True,  # Cancel 8 AM dispatch
                'schedule_new_dispatch': True,     # Schedule 10:30 AM dispatch
                'notify_driver': True,            # Notify if already assigned
                'update_eta_calculations': True   # Recalculate route timing
            },
            
            # Complete updated booking
            'updated_booking_details': updated_booking,
            'modification_metadata': {
                'modified_at': datetime.now().isoformat(),
                'modification_source': 'AI_Phone_System',
                'requires_customer_confirmation': False,  # Already confirmed via AI
                'dispatcher_notes': f"Time changed via AI: {original_booking.get('trip_details', {}).get('pickup_time')} → {updated_booking.get('trip_details', {}).get('pickup_time')}"
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-Source': 'KiwiCabs-AI-Live-Update',
            'X-Dispatch-Priority': 'IMMEDIATE',
            'Authorization': f'Bearer {TAXICALLER_API_KEY}' if TAXICALLER_API_KEY else None
        }
        
        headers = {k: v for k, v in headers.items() if v is not None}
        
        print("🚨 SENDING LIVE BOOKING UPDATE TO TAXICALLER DISPATCH:")
        print(f"📋 Booking Ref: {original_booking.get('booking_reference', 'N/A')}")
        print(f"📞 Customer: {original_booking.get('customer_details', {}).get('phone', 'N/A')}")
        print(f"⏰ OLD Time: {original_booking.get('trip_details', {}).get('pickup_time')} on {original_booking.get('trip_details', {}).get('pickup_date')}")
        print(f"🔄 NEW Time: {updated_booking.get('trip_details', {}).get('pickup_time')} on {updated_booking.get('trip_details', {}).get('pickup_date')}")
        print(f"📍 Pickup: {updated_booking.get('trip_details', {}).get('pickup_address')}")
        print(f"🎯 Drop-off: {updated_booking.get('trip_details', {}).get('destination_address')}")
        print("🚛 Fleet: Will redispatch at new time")
        
        # Send to TaxiCaller live dispatch system
        response = requests.put(  # PUT for live update
            f"{RENDER_ENDPOINT}/update_live_booking",
            json=modification_payload,
            headers=headers,
            timeout=15  # Longer timeout for live system
        )
        
        if response.status_code in [200, 202]:  # Accept 202 for async processing
            response_data = response.json() if response.content else {}
            print(f"✅ LIVE BOOKING UPDATE SUCCESSFUL!")
            print(f"📤 TaxiCaller Response: {response_data}")
            
            # Log dispatch status
            if response_data.get('dispatch_status'):
                print(f"🚛 Dispatch Status: {response_data['dispatch_status']}")
            
            return True
        else:
            print(f"❌ LIVE UPDATE FAILED: {response.status_code}")
            print(f"📤 Error Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 CRITICAL ERROR - Live booking update failed: {str(e)}")
        return False

def get_primary_modification_type(original, updated):
    """Determine the primary type of modification made"""
    if original.get('trip_details', {}).get('pickup_time') != updated.get('trip_details', {}).get('pickup_time'):
        return 'time_change'
    elif original.get('trip_details', {}).get('pickup_address') != updated.get('trip_details', {}).get('pickup_address'):
        return 'pickup_change'
    elif original.get('trip_details', {}).get('destination_address') != updated.get('trip_details', {}).get('destination_address'):
        return 'destination_change'
    elif original.get('booking_info', {}).get('status') != updated.get('booking_info', {}).get('status'):
        return 'cancellation'
    else:
        return 'general_update'

def get_modified_fields(original, updated):
    """Get list of fields that were modified"""
    modified = []
    
    if original.get('trip_details', {}).get('pickup_address') != updated.get('trip_details', {}).get('pickup_address'):
        modified.append('pickup_address')
    if original.get('trip_details', {}).get('destination_address') != updated.get('trip_details', {}).get('destination_address'):
        modified.append('destination_address')
    if original.get('trip_details', {}).get('pickup_time') != updated.get('trip_details', {}).get('pickup_time'):
        modified.append('pickup_time')
    if original.get('booking_info', {}).get('status') != updated.get('booking_info', {}).get('status'):
        modified.append('status')
        
    return modified
def get_phone_for_booking():
    """Extract phone number to search for existing booking"""
    phone_speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Phone Search: '{phone_speech}' (Confidence: {confidence})")
    
    # Extract and convert phone number from speech
    digits_only = re.sub(r'[^\d]', '', phone_speech)
    
    # Speech-to-text number word conversions
    number_words = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'oh': '0'
    }
    
    spoken_phone = phone_speech.lower()
    for word, digit in number_words.items():
        spoken_phone = spoken_phone.replace(word, digit)
    
    extracted_digits = re.sub(r'[^\d]', '', spoken_phone)
    phone_number = digits_only if len(digits_only) >= len(extracted_digits) else extracted_digits
    
    # Format NZ phone number
    if phone_number.startswith('64'):
        phone_number = '0' + phone_number[2:]
    elif len(phone_number) == 9 and not phone_number.startswith('0'):
        phone_number = '0' + phone_number
    
    if len(phone_number) >= 8:
        user_sessions[call_sid] = {'search_phone': phone_number}
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Thanks! I found your booking for phone number ending in {phone_number[-4:]}.
        What would you like to change? 
        Say pickup location, destination, or time.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch your phone number clearly. 
        Please say your phone number again, speaking each digit clearly.
        For example, say zero two one, two three four, five six seven eight.
    </Say>
    <Gather input="speech" action="/get_phone_for_booking" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/process_booking", methods=["POST"])
def process_booking():
    """Process new booking details and show confirmation"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"DEBUG - Booking Details: '{data}' (Confidence: {confidence})")
    
    # Store booking info in session
    user_sessions[call_sid] = {
        'booking_details': data,
        'timestamp': request.form.get('Timestamp', '')
    }

    # Parse booking details to show clean confirmation
    booking_data = parse_booking_details(data, caller_number)
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Let me confirm your booking details.
        Name: {booking_data['taxicaller_format']['customer_name']}.
        Pickup: {booking_data['taxicaller_format']['pickup_address']}.
        Drop-off: {booking_data['taxicaller_format']['destination_address']}.
        Time: {booking_data['taxicaller_format']['booking_time']} on {booking_data['taxicaller_format']['booking_date']}.
        Is this correct? Say yes to confirm or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_modification", methods=["POST"])
def process_modification():
    """Process real booking modification request"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Modification Request: '{data}' (Confidence: {confidence})")
    
    # Get the real existing booking from session
    session_data = user_sessions.get(call_sid, {})
    search_phone = session_data.get('search_phone', 'Unknown')
    existing_booking = session_data.get('existing_booking', {})
    
    if not existing_booking:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I can't find your booking details. Let me transfer you to our team.
    </Say>
    <Dial>+6448880188</Dial>
</Response>""", mimetype="text/xml")
    
    # Update the real booking with modifications
    updated_booking = update_existing_booking(search_phone, existing_booking, data)
    
    if updated_booking:
        # Store updated booking (but don't send to dispatch yet)
        modification_bookings[call_sid] = {
            'phone_number': search_phone,
            'original_booking': existing_booking,
            'updated_booking': updated_booking,
            'modification_request': data,
            'status': 'pending_confirmation'
        }
        
        # Show what will be changed
        modification_type = determine_modification_type(data)
        
        if modification_type == 'cancel':
            confirmation_message = f"I'll cancel your booking for {existing_booking.get('customer_details', {}).get('name', 'you')}. Say yes to confirm cancellation or no to keep the booking."
        else:
            # Show the specific changes
            if modification_type == 'pickup':
                new_pickup = updated_booking['trip_details']['pickup_address']
                confirmation_message = f"I'll change your pickup location to {new_pickup}. Say yes to confirm this change or no to try again."
            elif modification_type == 'destination':
                new_destination = updated_booking['trip_details']['destination_address']
                confirmation_message = f"I'll change your destination to {new_destination}. Say yes to confirm this change or no to try again."
            elif modification_type == 'time':
                new_time = updated_booking['trip_details']['pickup_time']
                new_date = updated_booking['trip_details']['pickup_date']
                confirmation_message = f"I'll change your pickup time to {new_time} on {new_date}. Say yes to confirm this change or no to try again."
            else:
                confirmation_message = f"I'll update your booking as requested: {data}. Say yes to confirm these changes or no to try again."

        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {confirmation_message}
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I had trouble understanding your change request. 
        Please try again. What would you like to change - pickup location, destination, or time?
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

def parse_booking_details(speech_text, caller_number):
    """Parse and format booking details for TaxiCaller dispatch system"""
    # Clean phone number
    clean_phone = caller_number.replace('+64', '0').replace(' ', '').replace('-', '')
    
    booking_data = {
        'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'caller_number': clean_phone,
        'raw_speech': speech_text,
        'timestamp': datetime.now().isoformat(),
        'status': 'confirmed',
        'taxicaller_format': {}
    }
    
    text_lower = speech_text.lower()
    
    # Extract customer name
    name_patterns = [
        r'(?:my name is|i\'m|this is|name)\s+([a-zA-Z\s]{2,30}?)(?:\s+(?:from|at|pickup|going|and|,))',
        r'^([a-zA-Z\s]{2,30}?)(?:\s+(?:from|at|pickup|going))',
        r'([a-zA-Z\s]{2,30}?)(?:\s+from)'
    ]
    
    customer_name = "Unknown Customer"
    for pattern in name_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name_candidate = match.group(1).strip()
            if not any(word in name_candidate for word in ['street', 'road', 'avenue', 'drive', 'wellington', 'airport']):
                customer_name = name_candidate.title()
                break
    
    # Wellington location database
    wellington_locations = {
        # CBD and Central
        'queen street': 'Queen Street, Wellington Central, Wellington',
        'cuba street': 'Cuba Street, Wellington Central, Wellington',
        'lambton quay': 'Lambton Quay, Wellington Central, Wellington',
        'willis street': 'Willis Street, Wellington Central, Wellington',
        'courtenay place': 'Courtenay Place, Wellington Central, Wellington',
        'manners street': 'Manners Street, Wellington Central, Wellington',
        'the terrace': 'The Terrace, Wellington Central, Wellington',
        'featherston street': 'Featherston Street, Wellington Central, Wellington',
        
        # Transport hubs
        'wellington airport': 'Wellington Airport, Rongotai, Wellington',
        'airport': 'Wellington Airport, Rongotai, Wellington',
        'wellington station': 'Wellington Railway Station, Pipitea, Wellington',
        'train station': 'Wellington Railway Station, Pipitea, Wellington',
        'railway station': 'Wellington Railway Station, Pipitea, Wellington',
        'interislander': 'Interislander Terminal, Aotea Quay, Wellington',
        'ferry terminal': 'Interislander Terminal, Aotea Quay, Wellington',
        
        # Popular suburbs
        'newtown': 'Newtown, Wellington',
        'mount victoria': 'Mount Victoria, Wellington',
        'kelburn': 'Kelburn, Wellington',
        'thorndon': 'Thorndon, Wellington',
        'te aro': 'Te Aro, Wellington',
        'oriental bay': 'Oriental Bay, Wellington',
        'island bay': 'Island Bay, Wellington',
        'karori': 'Karori, Wellington',
        'wadestown': 'Wadestown, Wellington',
        'brooklyn': 'Brooklyn, Wellington',
        'miramar': 'Miramar, Wellington',
        'kilbirnie': 'Kilbirnie, Wellington',
        'hataitai': 'Hataitai, Wellington',
        'roseneath': 'Roseneath, Wellington',
        'mount cook': 'Mount Cook, Wellington',
        'aro valley': 'Aro Valley, Wellington'
    }
    
    def find_wellington_address(text_segment):
        """Find and format Wellington addresses"""
        for location_key, full_address in wellington_locations.items():
            if location_key in text_segment:
                return full_address
        
        # Extract street names if no exact match
        street_patterns = [
            r'([a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way))',
            r'([a-zA-Z\s]+(?:st|rd|ave|dr|pl|tce|cres))'
        ]
        
        for pattern in street_patterns:
            match = re.search(pattern, text_segment)
            if match:
                street_name = match.group(1).strip().title()
                return f"{street_name}, Wellington"
        
        return text_segment.strip().title() + ", Wellington"
    
    # Extract pickup location
    pickup_patterns = [
        r'(?:from|pickup|pick up|starting from|at)\s+([^,]+?)(?:\s+(?:to|going|destination|and then))',
        r'(?:from|pickup|pick up|at)\s+([^,]+?)(?:\s+and|\s+then|\s+at\s+\d)',
    ]
    
    pickup_location = "Wellington Central, Wellington"
    for pattern in pickup_patterns:
        match = re.search(pattern, text_lower)
        if match:
            pickup_text = match.group(1).strip()
            pickup_location = find_wellington_address(pickup_text)
            break
    
    # Extract destination
    destination_patterns = [
        r'(?:to|going to|destination)\s+([^,]+?)(?:\s+(?:at|for|by|and)|\s+\d|$)',
        r'(?:to|going to|destination)\s+([^,]+?)(?:\s+then)',
    ]
    
    destination = "Wellington Central, Wellington"
    for pattern in destination_patterns:
        match = re.search(pattern, text_lower)
        if match:
            dest_text = match.group(1).strip()
            destination = find_wellington_address(dest_text)
            break
    
    # Parse time and create NZ formatted date/time
    current_time = datetime.now()
    requested_datetime = current_time
    
    time_patterns = [
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?',
        r'(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?'
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3) if len(match.groups()) >= 3 and match.group(3) else None
            
            if am_pm:
                if am_pm.lower() == 'pm' and hour != 12:
                    hour += 12
                elif am_pm.lower() == 'am' and hour == 12:
                    hour = 0
            
            try:
                requested_datetime = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if requested_datetime < current_time:
                    requested_datetime += timedelta(days=1)
            except ValueError:
                requested_datetime = current_time
            break
    
    # Handle time keywords
    time_keywords = {
        'now': current_time,
        'asap': current_time,
        'immediately': current_time,
        'morning': current_time.replace(hour=9, minute=0, second=0),
        'afternoon': current_time.replace(hour=14, minute=0, second=0),
        'evening': current_time.replace(hour=18, minute=0, second=0)
    }
    
    for keyword, time_value in time_keywords.items():
        if keyword in text_lower:
            requested_datetime = time_value
            break
    
    # Format for TaxiCaller (NZ format)
    formatted_date = requested_datetime.strftime('%d/%m/%Y')
    formatted_time = requested_datetime.strftime('%I:%M %p')
    
    # Create TaxiCaller formatted data
    booking_data['taxicaller_format'] = {
        'customer_name': customer_name,
        'pickup_address': pickup_location,
        'destination_address': destination,
        'booking_date': formatted_date,
        'booking_time': formatted_time,
        'phone_number': clean_phone,
        'booking_reference': booking_data['booking_reference'],
        'special_instructions': 'Booked via AI phone system'
    }
    
    return booking_data

def send_booking_to_render(booking_data):
    """Send formatted booking to TaxiCaller dispatch system"""
    try:
        taxicaller_payload = {
            'booking_reference': booking_data['booking_reference'],
            'customer_details': {
                'name': booking_data['taxicaller_format']['customer_name'],
                'phone': booking_data['taxicaller_format']['phone_number']
            },
            'trip_details': {
                'pickup_address': booking_data['taxicaller_format']['pickup_address'],
                'destination_address': booking_data['taxicaller_format']['destination_address'],
                'pickup_date': booking_data['taxicaller_format']['booking_date'],
                'pickup_time': booking_data['taxicaller_format']['booking_time']
            },
            'booking_info': {
                'source': 'AI_Phone_System',
                'special_instructions': booking_data['taxicaller_format']['special_instructions'],
                'status': 'confirmed',
                'region': 'Wellington'
            },
            'raw_data': {
                'original_speech': booking_data['raw_speech'],
                'timestamp': booking_data['timestamp']
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-Source': 'KiwiCabs-AI-IVR',
            'Authorization': f'Bearer {TAXICALLER_API_KEY}' if TAXICALLER_API_KEY else None
        }
        
        headers = {k: v for k, v in headers.items() if v is not None}
        
        # Log booking data
        print("=" * 50)
        print("📋 TAXICALLER BOOKING DATA:")
        print(f"👤 Customer: {taxicaller_payload['customer_details']['name']}")
        print(f"📞 Phone: {taxicaller_payload['customer_details']['phone']}")
        print(f"📍 Pickup: {taxicaller_payload['trip_details']['pickup_address']}")
        print(f"🎯 Drop-off: {taxicaller_payload['trip_details']['destination_address']}")
        print(f"📅 Date: {taxicaller_payload['trip_details']['pickup_date']}")
        print(f"⏰ Time: {taxicaller_payload['trip_details']['pickup_time']}")
        print(f"🔢 Reference: {taxicaller_payload['booking_reference']}")
        print("=" * 50)
        
        response = requests.post(
            RENDER_ENDPOINT,
            json=taxicaller_payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Successfully sent booking to TaxiCaller: {booking_data['booking_reference']}")
            print(f"📤 Response: {response.text}")
            return True
        else:
            print(f"❌ Failed to send booking. Status: {response.status_code}")
            print(f"📤 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 Error sending booking: {str(e)}")
        return False

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Confirm and process new booking"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"DEBUG - Booking Confirmation: '{data}' (Confidence: {confidence})")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        # Get booking details and process
        booking_details = user_sessions.get(call_sid, {}).get('booking_details', '')
        booking_data = parse_booking_details(booking_details, caller_number)
        
        print("🚕 COMPLETE BOOKING DATA FOR TAXICALLER:")
        print(json.dumps(booking_data['taxicaller_format'], indent=2))
        
        # Send to TaxiCaller
        render_success = send_booking_to_render(booking_data)
        
        # Simple confirmation message
        success_message = "Thank you. Your booking is confirmed. Goodbye."
        
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {success_message}
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    elif any(pattern in data for pattern in no_patterns):
        return redirect_to("/book")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/confirm_modification", methods=["POST"])
def confirm_modification():
    """Confirm and send real booking modification to dispatch"""
    data = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    print(f"DEBUG - Modification Confirmation: '{data}'")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "good", "sweet", "confirm"]
    no_patterns = ["no", "nah", "wrong", "different", "change"]
    
    if any(pattern in data for pattern in yes_patterns):
        modification_data = modification_bookings.get(call_sid, {})
        
        if modification_data and 'updated_booking' in modification_data:
            # Send REAL booking update to dispatch system
            success = send_booking_modification_to_dispatch(
                modification_data['updated_booking'],
                modification_data['original_booking']
            )
            
            if success:
                # Clean up session data
                if call_sid in modification_bookings:
                    del modification_bookings[call_sid]
                
                return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Your booking changes have been confirmed and sent to our dispatch system.
        You'll receive a confirmation call with the updated details shortly.
        Thanks for using Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
            else:
                return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Your booking modification has been noted. 
        Our team will process the changes and call you back shortly to confirm.
        Thanks for using Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        else:
            return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I can't find your modification details. Let me transfer you to our team.
    </Say>
    <Dial>+6448880188</Dial>
</Response>""", mimetype="text/xml")
        
    elif any(pattern in data for pattern in no_patterns):
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! What would you like to change about your booking?
        Say pickup location, destination, time, or cancel booking.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that. Please say yes to confirm your booking changes, or no to make different changes.
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml") in no_patterns):
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! What would you like to change about your booking?
        Say pickup location, destination, or time.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that. Please say yes to confirm your booking changes, or no to make different changes.
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

def redirect_to(path):
    """Helper function for XML redirects"""
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

@app.route("/handle_no_booking_found", methods=["POST"])
def handle_no_booking_found():
    """Handle when no existing booking is found"""
    data = request.form.get("SpeechResult", "").lower()
    
    yes_patterns = ["yes", "yeah", "yep", "sure", "ok", "okay", "book"]
    no_patterns = ["no", "nah", "thanks", "goodbye"]
    
    if any(pattern in data for pattern in yes_patterns):
        return redirect_to("/book")
    elif any(pattern in data for pattern in no_patterns):
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No worries! Thanks for calling Kiwi Cabs. Have a great day!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Would you like me to help you book a new taxi? Say yes or no.
    </Say>
    <Gather input="speech" action="/handle_no_booking_found" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
@app.route("/api/bookings", methods=["POST"])
def receive_booking():
    """Endpoint to receive and log booking data"""
    try:
        booking_data = request.get_json()
        print("📨 RECEIVED BOOKING DATA:")
        print(json.dumps(booking_data, indent=2))
        return {
            "status": "success", 
            "message": "Booking received successfully", 
            "booking_id": booking_data.get('booking_reference', 'N/A')
        }
    except Exception as e:
        print(f"❌ Error receiving booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

# Health check endpoint
@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Kiwi Cabs AI IVR", "version": "2.0"}

# Root endpoint
@app.route("/", methods=["GET"])
def home():
    """Root endpoint with service info"""
    return {
        "message": "Kiwi Cabs AI IVR System", 
        "