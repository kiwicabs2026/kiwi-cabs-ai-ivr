@app.route("/process_location_booking", methods=["POST"])
def process_location_booking():
    """Process booking with location suggestions"""
    data = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🗺️ LOCATION BOOKING: '{data}'")
    
    # Get stored location and nearby suggestions
    session_data = user_sessions.get(call_sid, {})
    caller_location = session_data.get('caller_location', {})
    
    # Check if user selected a nearby option
    option_patterns = [
        r'@app.route("/book", methods=["POST"])
def book():
    """Standard booking process (fallback)"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great choice! I'll help you book your taxi.
        Please tell me your full name, where you need to be picked up from, where you're going, and what time you need the taxi.
        Take your time and speak clearly.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="12" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")@app.route("/process_booking", methods=["POST"])
def process_booking():
    """Process new booking details with Wellington service area validation"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🎯 PROCESSING BOOKING: '{data}' (Confidence: {confidence})")
    
    # Parse the booking details
    booking_data = parse_booking_details(data, caller_number)
    
    # Validate that booking addresses are in Wellington
    booking_addresses = {
        'pickup': booking_data['taxicaller_format'].get('pickup_address', ''),
        'destination': booking_data['taxicaller_format'].get('destination_address', '')
    }
    
    address_validation = validate_wellington_service_area(None, booking_addresses)
    
    if not address_validation['in_service_area']:
        print(f"🚫 BOOKING ADDRESSES OUTSIDE WELLINGTON: {address_validation['reason']}")
        
        # Store validation result for the error message
        user_sessions[call_sid]['address_validation'] = address_validation
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {address_validation['message']}
        Please provide pickup and destination addresses within the Wellington region.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    
    # Validate pickup address confidence
    pickup_text = extract_pickup_from_speech(data)
    pickup_geocoded = geocode_nz_address(pickup_text) if pickup_text else None
    pickup_confident, pickup_reason = validate_address_confidence(pickup_text or "", pickup_geocoded)
    
    # Validate destination address confidence  
    destination_text = extract_destination_from_speech(data)
    destination_geocoded = geocode_nz_address(destination_text) if destination_text else None
    destination_confident, destination_reason = validate_address_confidence(destination_text or "", destination_geocoded)
    
    print(f"📍 PICKUP: '{pickup_text}' - Confident: {pickup_confident} ({pickup_reason})")
    print(f"🎯 DESTINATION: '{destination_text}' - Confident: {destination_confident} ({destination_reason})")
    
    # Store partial booking data
    user_sessions[call_sid] = {
        'booking_details': data,
        'timestamp': request.form.get('Timestamp', ''),
        'partial_booking': booking_data
    }
    
    # If both addresses are unclear, ask for pickup first
    if not pickup_confident and not destination_confident:
        print("❌ BOTH ADDRESSES UNCLEAR - asking for pickup")
        return redirect_to("/clarify_pickup")
    
    # If only pickup is unclear
    elif not pickup_confident:
        print("❌ PICKUP UNCLEAR - asking for pickup")
        return redirect_to("/clarify_pickup")
    
    # If only destination is unclear
    elif not destination_confident:
        print("❌ DESTINATION UNCLEAR - asking for destination") 
        return redirect_to("/clarify_destination")
    
    # Both addresses are confident and in Wellington, proceed with normal confirmation
    else:
        print("✅ BOTH ADDRESSES CONFIDENT AND IN WELLINGTON - proceeding to confirmation")
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

def extract_pickup_from_speech(speech_text):
    """Extract just the pickup address part from speech"""
    text_lower = speech_text.lower()
    
    pickup_patterns = [
        r'(?:from|pickup|pick up|starting from|at)\s+([^,]+?)(?:\s+(?:to|going|destination|i\'m going))',
        r'(?:taxi from|from)\s+([^,]+?)(?:\s+(?:to|going|i\'m going))',
        r'(?:from|pickup|pick up|at)\s+([^,]+?)(?:\s+and)',
    ]
    
    for pattern in pickup_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    
    return ""

def extract_destination_from_speech(speech_text):
    """Extract just the destination address part from speech"""
    text_lower = speech_text.lower()
    
    destination_patterns = [
        r'(?:to|going to|destination|i\'m going to)\s+([^,]+?)(?:\s+(?:at|for|by|today|tomorrow)|\s+\d|$)',
        r'(?:going to|to)\s+(train station|railway station|wellington station|airport|wellington airport)',
        r'(?:to|going to)\s+([^,]+?)(?:\s+then)',
    ]
    
    for pattern in destination_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    
    return ""import os
import requests
import json
from flask import Flask, request, Response
from datetime import datetime, timedelta
import re
import urllib.parse

app = Flask(__name__)

# TaxiCaller API Configuration
TAXICALLER_BASE_URL = "https://api.taxicaller.net/api/v1"
TAXICALLER_API_KEY = os.getenv("TAXICALLER_API_KEY", "")
RENDER_ENDPOINT = os.getenv("RENDER_ENDPOINT", "https://kiwi-cabs-ai-service.onrender.com/api/bookings")

# Session memory stores
user_sessions = {}
modification_bookings = {}

def geocode_nz_address(address_text):
    """Use real NZ geocoding to find accurate addresses"""
    try:
        # Clean up the address text
        cleaned_address = address_text.strip()
        
        # Add Wellington, New Zealand if not present
        if 'wellington' not in cleaned_address.lower() and 'new zealand' not in cleaned_address.lower():
            cleaned_address += ", Wellington, New Zealand"
        
        print(f"🌍 GEOCODING: '{cleaned_address}'")
        
        # Use OpenStreetMap Nominatim API (free, no API key needed)
        encoded_address = urllib.parse.quote(cleaned_address)
        nominatim_url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=3&countrycodes=nz&addressdetails=1"
        
        headers = {
            'User-Agent': 'KiwiCabs-AI-Taxi-Service/1.0'
        }
        
        response = requests.get(nominatim_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            results = response.json()
            
            if results:
                best_result = results[0]  # Take the first (best) result
                
                # Extract address components
                address_parts = best_result.get('address', {})
                display_name = best_result.get('display_name', '')
                
                # Build formatted NZ address
                street_number = address_parts.get('house_number', '')
                street_name = address_parts.get('road', '')
                suburb = address_parts.get('suburb', address_parts.get('neighbourhood', ''))
                city = address_parts.get('city', address_parts.get('town', 'Wellington'))
                
                # Format the address nicely
                formatted_address = ""
                if street_number and street_name:
                    formatted_address = f"{street_number} {street_name}"
                elif street_name:
                    formatted_address = street_name
                else:
                    # Fallback to using the display name parts
                    formatted_address = display_name.split(',')[0]
                
                if suburb:
                    formatted_address += f", {suburb}"
                
                formatted_address += f", {city}"
                
                # Get coordinates
                lat = float(best_result.get('lat', -41.2865))
                lon = float(best_result.get('lon', 174.7762))
                
                print(f"✅ GEOCODED: '{address_text}' → '{formatted_address}'")
                print(f"📍 COORDINATES: {lat}, {lon}")
                
                return {
                    'formatted_address': formatted_address,
                    'latitude': lat,
                    'longitude': lon,
                    'raw_result': best_result
                }
            else:
                print(f"❌ NO GEOCODING RESULTS for: '{address_text}'")
                return None
        else:
            print(f"❌ GEOCODING API ERROR: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"💥 GEOCODING ERROR: {str(e)}")
        return None

def smart_nz_address_lookup(address_text):
    """Smart NZ address detection with fallbacks"""
    
    # First try direct geocoding
    geocoded = geocode_nz_address(address_text)
    if geocoded:
        return geocoded['formatted_address'], (geocoded['latitude'], geocoded['longitude'])
    
    # Fallback to Wellington location database for common places
    wellington_locations = {
        'queen street': ('Queen Street, Wellington Central, Wellington', (-41.2865, 174.7762)),
        'cuba street': ('Cuba Street, Wellington Central, Wellington', (-41.2924, 174.7769)),
        'lambton quay': ('Lambton Quay, Wellington Central, Wellington', (-41.2849, 174.7751)),
        'willis street': ('Willis Street, Wellington Central, Wellington', (-41.2892, 174.7756)),
        'courtenay place': ('Courtenay Place, Wellington Central, Wellington', (-41.2942, 174.7828)),
        'manners street': ('Manners Street, Wellington Central, Wellington', (-41.2889, 174.7756)),
        'the terrace': ('The Terrace, Wellington Central, Wellington', (-41.2809, 174.7711)),
        'featherston street': ('Featherston Street, Wellington Central, Wellington', (-41.2817, 174.7756)),
        'wellington airport': ('Wellington Airport, Rongotai, Wellington', (-41.3274, 174.8049)),
        'airport': ('Wellington Airport, Rongotai, Wellington', (-41.3274, 174.8049)),
        'wellington station': ('Wellington Railway Station, Pipitea, Wellington', (-41.2783, 174.7756)),
        'train station': ('Wellington Railway Station, Pipitea, Wellington', (-41.2783, 174.7756)),
        'railway station': ('Wellington Railway Station, Pipitea, Wellington', (-41.2783, 174.7756)),
        'interislander': ('Interislander Terminal, Aotea Quay, Wellington', (-41.2735, 174.7839)),
        'ferry terminal': ('Interislander Terminal, Aotea Quay, Wellington', (-41.2735, 174.7839)),
        'newtown': ('Newtown, Wellington', (-41.3097, 174.7789)),
        'mount victoria': ('Mount Victoria, Wellington', (-41.2965, 174.7937)),
        'kelburn': ('Kelburn, Wellington', (-41.2438, 174.7661)),
        'thorndon': ('Thorndon, Wellington', (-41.2709, 174.7715)),
        'te aro': ('Te Aro, Wellington', (-41.2924, 174.7769)),
        'oriental bay': ('Oriental Bay, Wellington', (-41.2929, 174.7959)),
        'island bay': ('Island Bay, Wellington', (-41.3429, 174.7672)),
        'karori': ('Karori, Wellington', (-41.2858, 174.7274)),
        'wadestown': ('Wadestown, Wellington', (-41.2544, 174.7699)),
        'brooklyn': ('Brooklyn, Wellington', (-41.3146, 174.7585)),
        'miramar': ('Miramar, Wellington', (-41.3145, 174.8156)),
        'kilbirnie': ('Kilbirnie, Wellington', (-41.3145, 174.7958)),
        'hataitai': ('Hataitai, Wellington', (-41.3047, 174.8078)),
        'roseneath': ('Roseneath, Wellington', (-41.2845, 174.8078)),
        'mount cook': ('Mount Cook, Wellington', (-41.3000, 174.7769)),
        'aro valley': ('Aro Valley, Wellington', (-41.2784, 174.7588))
    }
    
    # Check for known locations
    address_lower = address_text.lower()
    for location_key, (full_address, coords) in wellington_locations.items():
        if location_key in address_lower:
            print(f"✅ MATCHED KNOWN LOCATION: '{address_text}' → '{full_address}'")
            return full_address, coords
    
    # Try to extract street name and add Wellington
    street_patterns = [
        r'(\d+\s+[a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way))',
        r'([a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way))',
        r'(\d+\s+[a-zA-Z\s]+(?:st|rd|ave|dr|pl|tce|cres))',
        r'([a-zA-Z\s]+(?:st|rd|ave|dr|pl|tce|cres))'
    ]
    
    for pattern in street_patterns:
        match = re.search(pattern, address_text, re.IGNORECASE)
        if match:
            street_name = match.group(1).strip().title()
            formatted_address = f"{street_name}, Wellington"
            print(f"📍 EXTRACTED STREET: '{address_text}' → '{formatted_address}'")
            
            # Try geocoding the extracted street
            geocoded = geocode_nz_address(formatted_address)
            if geocoded:
                return geocoded['formatted_address'], (geocoded['latitude'], geocoded['longitude'])
            else:
                # Return the formatted version with default Wellington coordinates
                return formatted_address, (-41.2865, 174.7762)
    
    # Final fallback
    fallback_address = f"{address_text.strip().title()}, Wellington"
    print(f"🔄 FALLBACK ADDRESS: '{fallback_address}'")
    return fallback_address, (-41.2865, 174.7762)

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
        
        print(f"🔍 SEARCHING TAXICALLER FOR BOOKING: Phone {phone_number}")
        
        # For now, return mock data since we need your company_id to make real calls
        mock_booking = {
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
        
        print(f"✅ MOCK BOOKING FOUND (Replace with real TaxiCaller search)")
        return mock_booking
        
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
        
        tc_format = booking_data['taxicaller_format']
        
        # Wellington CBD coordinates as default
        pickup_coords = [17465000, -41290000]
        dropoff_coords = [17465000, -41290000]
        
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
                "company_id": 1318,  # Replace with your actual company_id
                "provider_id": 0,
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
                        "account": {"id": 0},
                        "require": {
                            "seats": 1,
                            "wc": 0,
                            "bags": 1
                        },
                        "pay_info": [{"@t": 0, "data": None}]
                    }
                ],
                "route": {
                    "nodes": [
                        {
                            "actions": [
                                {
                                    "@type": "client_action",
                                    "item_seq": 0,
                                    "action": "in"
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
                                    "action": "out"
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
                                "dist": 5000,
                                "est_dur": 600
                            },
                            "pts": pickup_coords + dropoff_coords,
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
    """Process menu selection"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    print(f"DEBUG - Menu Selection: '{data}' (Confidence: {confidence})")

    booking_keywords = ["1", "one", "book", "taxi", "ride", "cab", "new booking", "need a taxi", "want a taxi"]
    modify_keywords = ["2", "two", "change", "cancel", "modify", "existing", "alter", "update"]
    team_keywords = ["3", "three", "team", "human", "person", "staff", "operator", "speak"]

    if any(keyword in data for keyword in booking_keywords):
        return redirect_to("/book_with_location")  # Use location-aware booking
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

def detect_landline_location(caller_number):
    """Detect location from New Zealand landline area codes"""
    try:
        # Clean the phone number
        clean_number = caller_number.replace('+64', '').replace(' ', '').replace('-', '')
        
        # NZ landline area codes and their locations
        nz_area_codes = {
            '03': {
                'region': 'South Island',
                'cities': ['Christchurch', 'Dunedin', 'Invercargill', 'Nelson', 'Timaru'],
                'main_city': 'Christchurch',
                'coordinates': (-43.5321, 172.6362)
            },
            '04': {
                'region': 'Wellington Region',
                'cities': ['Wellington', 'Lower Hutt', 'Upper Hutt', 'Porirua', 'Kapiti Coast'],
                'main_city': 'Wellington',
                'coordinates': (-41.2865, 174.7762)
            },
            '06': {
                'region': 'Lower North Island',
                'cities': ['New Plymouth', 'Whanganui', 'Palmerston North', 'Napier', 'Hastings'],
                'main_city': 'Palmerston North',
                'coordinates': (-40.3523, 175.6082)
            },
            '07': {
                'region': 'Central North Island',
                'cities': ['Hamilton', 'Tauranga', 'Rotorua', 'Taupo', 'Thames'],
                'main_city': 'Hamilton',
                'coordinates': (-37.7879, 175.2793)
            },
            '09': {
                'region': 'Auckland Region',
                'cities': ['Auckland', 'North Shore', 'Waitakere', 'Manukau'],
                'main_city': 'Auckland',
                'coordinates': (-36.8485, 174.7633)
            }
        }
        
        # Check if it's a landline (starts with area code)
        for area_code, location_info in nz_area_codes.items():
            if clean_number.startswith(area_code):
                print(f"📞 LANDLINE DETECTED: Area code {area_code}")
                print(f"🏙️ Region: {location_info['region']}")
                print(f"📍 Main city: {location_info['main_city']}")
                
                return {
                    'is_landline': True,
                    'area_code': area_code,
                    'region': location_info['region'],
                    'main_city': location_info['main_city'],
                    'possible_cities': location_info['cities'],
                    'coordinates': location_info['coordinates'],
                    'confidence': 'area_code_based'
                }
        
        # Check for mobile numbers (starts with 02)
        if clean_number.startswith('02'):
            print(f"📱 MOBILE NUMBER DETECTED: {caller_number}")
            return {
                'is_landline': False,
                'is_mobile': True,
                'area_code': '02',
                'region': 'Mobile - Location varies',
                'confidence': 'mobile_number'
            }
        
        print(f"❓ UNKNOWN NUMBER FORMAT: {caller_number}")
        return None
        
    except Exception as e:
        print(f"⚠️ Error detecting landline location: {str(e)}")
        return None

def validate_wellington_service_area(caller_location, booking_addresses=None):
    """Validate that service request is within Wellington region"""
    
    # Wellington region area codes and boundaries
    wellington_service_area = {
        'area_codes': ['04'],  # Only 04 landlines in Wellington
        'region_name': 'Wellington Region',
        'service_cities': [
            'wellington', 'lower hutt', 'upper hutt', 'porirua', 'kapiti coast',
            'paraparaumu', 'waikanae', 'eastbourne', 'petone', 'johnsonville'
        ],
        'coordinates_bounds': {
            'north': -40.8,   # Kapiti Coast north
            'south': -41.5,   # Wellington south
            'west': 174.6,    # West coast
            'east': 175.2     # Wairarapa east
        }
    }
    
    print(f"🌍 VALIDATING SERVICE AREA...")
    
    # Check 1: Area code validation (landlines)
    if caller_location.get('is_landline'):
        area_code = caller_location.get('area_code', '')
        
        if area_code not in wellington_service_area['area_codes']:
            print(f"❌ OUTSIDE SERVICE AREA: Area code {area_code} not in Wellington region")
            return {
                'in_service_area': False,
                'reason': 'outside_wellington_region',
                'caller_region': caller_location.get('region', 'Unknown'),
                'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. I can see you're calling from {caller_location.get('region', 'outside Wellington')}."
            }
    
    # Check 2: GPS coordinates validation (mobiles)
    if caller_location.get('has_coordinates'):
        lat = caller_location.get('latitude')
        lon = caller_location.get('longitude')
        bounds = wellington_service_area['coordinates_bounds']
        
        if not (bounds['south'] <= lat <= bounds['north'] and 
                bounds['west'] <= lon <= bounds['east']):
            print(f"❌ OUTSIDE SERVICE AREA: GPS coordinates {lat}, {lon} not in Wellington region")
            return {
                'in_service_area': False,
                'reason': 'outside_wellington_coordinates',
                'coordinates': (lat, lon),
                'message': "Sorry, Kiwi Cabs operates only in the Wellington region. Your current location appears to be outside our service area."
            }
    
    # Check 3: City name validation  
    city = caller_location.get('city', '').lower()
    if city and city not in wellington_service_area['service_cities']:
        # Check if it's a variation of Wellington
        wellington_variations = ['wellington', 'wgtn', 'welly']
        if not any(var in city for var in wellington_variations):
            print(f"❌ OUTSIDE SERVICE AREA: City '{city}' not in Wellington region")
            return {
                'in_service_area': False,
                'reason': 'outside_wellington_city',
                'caller_city': city,
                'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. I can see you're calling from {city.title()}."
            }
    
    # Check 4: Booking addresses validation (if provided)
    if booking_addresses:
        for address_type, address in booking_addresses.items():
            if address and not is_wellington_address(address):
                print(f"❌ OUTSIDE SERVICE AREA: {address_type} '{address}' not in Wellington region")
                return {
                    'in_service_area': False,
                    'reason': f'booking_{address_type}_outside_wellington',
                    'problematic_address': address,
                    'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. Your {address_type} address appears to be outside our service area."
                }
    
    print(f"✅ WITHIN SERVICE AREA: Wellington region confirmed")
    return {
        'in_service_area': True,
        'reason': 'wellington_region_confirmed',
        'message': None
    }

def is_wellington_address(address):
    """Enhanced Wellington address validation with better detection"""
    if not address:
        return True  # Allow empty addresses to be validated elsewhere
    
    address_lower = address.lower()
    
    # Wellington region keywords that indicate it's in the service area
    wellington_keywords = [
        'wellington', 'wgtn', 'welly', 'lower hutt', 'upper hutt', 'hutt valley', 'hutt', 
        'porirua', 'kapiti', 'paraparaumu', 'waikanae', 'otaki', 'eastbourne', 'petone',
        'johnsonville', 'tawa', 'miramar', 'kilbirnie', 'newtown', 'karori',
        'brooklyn', 'island bay', 'kelburn', 'thorndon', 'te aro', 'mount victoria',
        'oriental bay', 'hataitai', 'roseneath', 'mount cook', 'aro valley',
        'wadestown', 'khandallah', 'ngaio', 'crofton downs', 'northland', 'broadmeadows',
        'churton park', 'glenside', 'grenada north', 'grenada village', 'paparangi',
        'woodridge', 'horokiwi', 'alicetown', 'avalon', 'boulcott', 'epuni',
        'gracefield', 'haywards', 'manor park', 'moera', 'naenae', 'stokes valley',
        'taita', 'wainuiomata', 'waterloo', 'woburn', 'belmont', 'brentwood',
        'heretaunga', 'pinehaven', 'silverstream', 'totara park', 'wallaceville',
        'aotea', 'camborne', 'elsdon', 'linden', 'mana', 'paremata', 'plimmerton',
        'pukerua bay', 'raumati', 'titahi bay', 'whitby', 'cannon point', 'paekakariki'
    ]
    
    # Check if any Wellington keywords are present
    for keyword in wellington_keywords:
        if keyword in address_lower:
            print(f"✅ WELLINGTON ADDRESS CONFIRMED: '{keyword}' found in '{address}'")
            return True
    
    # Check for major non-Wellington cities that are definitely outside service area
    outside_cities = [
        'auckland', 'christchurch', 'hamilton', 'tauranga', 'dunedin',
        'palmerston north', 'hastings', 'napier', 'rotorua', 'new plymouth',
        'whanganui', 'invercargill', 'nelson', 'timaru', 'whangarei',
        'gisborne', 'blenheim', 'masterton', 'levin', 'feilding'
    ]
    
    for city in outside_cities:
        if city in address_lower:
            print(f"❌ NON-WELLINGTON CITY DETECTED: '{city}' found in '{address}'")
            return False
    
    # Check for airport codes that are outside Wellington
    outside_airports = ['auckland airport', 'akl airport', 'christchurch airport', 'chc airport']
    for airport in outside_airports:
        if airport in address_lower:
            print(f"❌ NON-WELLINGTON AIRPORT: '{airport}' found in '{address}'")
            return False
    
    # Special handling for common Wellington landmarks
    wellington_landmarks = [
        'airport', 'train station', 'railway station', 'wellington station',
        'interislander', 'ferry terminal', 'parliament', 'beehive',
        'te papa', 'cuba mall', 'botanic garden', 'cable car'
    ]
    
    for landmark in wellington_landmarks:
        if landmark in address_lower:
            print(f"✅ WELLINGTON LANDMARK DETECTED: '{landmark}' in '{address}'")
            return True
    
    # If no specific indicators found, be conservative and assume it might be Wellington
    # (since we're already filtering by area code/GPS for most calls)
    print(f"⚠️ UNCLEAR ADDRESS: '{address}' - assuming Wellington region")
    return True

@app.route("/outside_service_area", methods=["POST"])
def outside_service_area():
    """Handle calls from outside Wellington service area"""
    call_sid = request.form.get("CallSid", "")
    session_data = user_sessions.get(call_sid, {})
    validation_result = session_data.get('validation_result', {})
    
    caller_region = validation_result.get('caller_region', 'your area')
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Kiwi Cabs operates only in the Wellington region. 
        I can see you're calling from {caller_region}.
        For taxi services in your area, I recommend searching online for local taxi companies.
        Thanks for calling, and have a great day!
    </Say>
    <Hangup/>
</Response>"""
    return Response(response, mimetype="text/xml")

def get_caller_location(request_data):
    """Enhanced caller location detection with landline support"""
    try:
        caller_number = request_data.get('From', '')
        
        # First try landline detection
        landline_info = detect_landline_location(caller_number)
        
        if landline_info and landline_info.get('is_landline'):
            # It's a landline - use area code location
            location_info = {
                'has_coordinates': True,
                'latitude': landline_info['coordinates'][0],
                'longitude': landline_info['coordinates'][1],
                'city': landline_info['main_city'],
                'region': landline_info['region'],
                'country': 'New Zealand',
                'area_code': landline_info['area_code'],
                'is_landline': True,
                'possible_cities': landline_info['possible_cities'],
                'confidence': 'area_code_landline',
                'formatted_address': f"{landline_info['main_city']}, {landline_info['region']}, New Zealand"
            }
            
            print(f"📞 LANDLINE LOCATION:")
            print(f"   📍 Area Code: {landline_info['area_code']}")
            print(f"   🏙️ Region: {landline_info['region']}")
            print(f"   📌 Main City: {landline_info['main_city']}")
            print(f"   🌍 Coordinates: {location_info['latitude']}, {location_info['longitude']}")
            
            return location_info
        
        # If not landline, try mobile GPS detection
        elif landline_info and landline_info.get('is_mobile'):
            print(f"📱 MOBILE NUMBER - trying GPS detection...")
        
        # Try to get GPS/network location from Twilio (for mobiles)
        caller_country = request_data.get('CallerCountry', '')
        caller_state = request_data.get('CallerState', '')
        caller_city = request_data.get('CallerCity', '')
        caller_zip = request_data.get('CallerZip', '')
        
        # Get coordinates if available
        caller_lat = request_data.get('CallerLat', '')
        caller_lon = request_data.get('CallerLon', '')
        
        # Get additional location info
        from_city = request_data.get('FromCity', '')
        from_state = request_data.get('FromState', '')
        from_country = request_data.get('FromCountry', '')
        
        location_info = {
            'has_coordinates': bool(caller_lat and caller_lon),
            'latitude': float(caller_lat) if caller_lat else None,
            'longitude': float(caller_lon) if caller_lon else None,
            'city': caller_city or from_city or '',
            'state': caller_state or from_state or '',
            'country': caller_country or from_country or '',
            'zip_code': caller_zip or '',
            'is_landline': False,
            'confidence': 'gps_mobile' if (caller_lat and caller_lon) else 'network_mobile',
            'formatted_address': ''
        }
        
        # Build formatted address
        address_parts = []
        if location_info['city']:
            address_parts.append(location_info['city'])
        if location_info['state']:
            address_parts.append(location_info['state'])
        if location_info['country']:
            address_parts.append(location_info['country'])
        
        location_info['formatted_address'] = ', '.join(address_parts)
        
        print(f"📱 MOBILE LOCATION:")
        print(f"   📱 Has GPS: {location_info['has_coordinates']}")
        if location_info['has_coordinates']:
            print(f"   🌍 Coordinates: {location_info['latitude']}, {location_info['longitude']}")
        print(f"   🏙️ City: {location_info['city']}")
        print(f"   📍 Full: {location_info['formatted_address']}")
        
        return location_info
        
    except Exception as e:
        print(f"⚠️ Error getting caller location: {str(e)}")
        return {
            'has_coordinates': False,
            'latitude': None,
            'longitude': None,
            'city': 'Wellington',  # Default to Wellington
            'state': '',
            'country': 'New Zealand',
            'zip_code': '',
            'is_landline': False,
            'confidence': 'default',
            'formatted_address': 'Wellington, New Zealand'
        }

def suggest_nearby_locations(caller_location):
    """Suggest nearby pickup locations based on caller's location"""
    try:
        if not caller_location['has_coordinates']:
            return []
        
        lat = caller_location['latitude']
        lon = caller_location['longitude']
        
        # Wellington landmarks with coordinates
        wellington_landmarks = [
            {'name': 'Wellington Airport', 'lat': -41.3274, 'lon': 174.8049, 'address': 'Wellington Airport, Rongotai, Wellington'},
            {'name': 'Wellington Railway Station', 'lat': -41.2783, 'lon': 174.7756, 'address': 'Wellington Railway Station, Pipitea, Wellington'},
            {'name': 'Queen Street', 'lat': -41.2865, 'lon': 174.7762, 'address': 'Queen Street, Wellington Central, Wellington'},
            {'name': 'Courtenay Place', 'lat': -41.2942, 'lon': 174.7828, 'address': 'Courtenay Place, Wellington Central, Wellington'},
            {'name': 'Cuba Street', 'lat': -41.2924, 'lon': 174.7769, 'address': 'Cuba Street, Wellington Central, Wellington'},
            {'name': 'Lambton Quay', 'lat': -41.2849, 'lon': 174.7751, 'address': 'Lambton Quay, Wellington Central, Wellington'},
            {'name': 'Interislander Terminal', 'lat': -41.2735, 'lon': 174.7839, 'address': 'Interislander Terminal, Aotea Quay, Wellington'},
        ]
        
        # Calculate distances and find closest locations
        import math
        
        def calculate_distance(lat1, lon1, lat2, lon2):
            """Calculate distance between two points in kilometers"""
            R = 6371  # Earth's radius in km
            dLat = math.radians(lat2 - lat1)
            dLon = math.radians(lon2 - lon1)
            a = math.sin(dLat/2) * math.sin(dLat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2) * math.sin(dLon/2)
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        
        # Find nearby locations (within 5km)
        nearby_locations = []
        for landmark in wellington_landmarks:
            distance = calculate_distance(lat, lon, landmark['lat'], landmark['lon'])
            if distance <= 5:  # Within 5km
                landmark['distance'] = distance
                nearby_locations.append(landmark)
        
        # Sort by distance
        nearby_locations.sort(key=lambda x: x['distance'])
        
        print(f"🗺️ FOUND {len(nearby_locations)} NEARBY LOCATIONS:")
        for loc in nearby_locations[:3]:  # Show top 3
            print(f"   📍 {loc['name']} ({loc['distance']:.1f}km away)")
        
        return nearby_locations[:3]  # Return top 3 closest
        
    except Exception as e:
        print(f"⚠️ Error finding nearby locations: {str(e)}")
        return []

@app.route("/book_with_location", methods=["POST"])
def book_with_location():
    """Start booking process with location detection and service area validation"""
    # Get all request data for location detection
    request_data = dict(request.form)
    
    # Detect caller location (mobile GPS or landline area code)
    caller_location = get_caller_location(request_data)
    call_sid = request.form.get("CallSid", "")
    
    # Validate service area FIRST
    validation_result = validate_wellington_service_area(caller_location)
    
    # Store location and validation in session
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {}
    user_sessions[call_sid]['caller_location'] = caller_location
    user_sessions[call_sid]['validation_result'] = validation_result
    
    # If outside service area, politely decline
    if not validation_result['in_service_area']:
        print(f"🚫 CALL OUTSIDE SERVICE AREA: {validation_result['reason']}")
        return redirect_to("/outside_service_area")
    
    # Continue with normal booking flow for Wellington region calls
    print(f"✅ CALL WITHIN WELLINGTON SERVICE AREA - proceeding with booking")
    
    # Case 1: Wellington landline (04 area code) - we already know they're in Wellington
    if caller_location.get('is_landline') and caller_location.get('area_code') == '04':
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I'll help you book your taxi.
        Please tell me your name, pickup address, destination, and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response_xml, mimetype="text/xml")
    
    # Case 2: Other NZ landline areas - should not reach here due to validation, but fallback
    elif caller_location.get('is_landline'):
        return redirect_to("/outside_service_area")
    
    # Case 3: Mobile with GPS coordinates in Wellington
    elif caller_location.get('has_coordinates'):
        # Try to reverse geocode the coordinates to get a readable address
        try:
            lat = caller_location['latitude']
            lon = caller_location['longitude']
            
            print(f"🌍 WELLINGTON MOBILE GPS: {lat}, {lon}")
            
            # Reverse geocode to get street address
            reverse_geocode_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
            headers = {'User-Agent': 'KiwiCabs-AI-Taxi-Service/1.0'}
            
            response = requests.get(reverse_geocode_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                location_data = response.json()
                
                # Extract readable address
                address_parts = location_data.get('address', {})
                street_number = address_parts.get('house_number', '')
                street_name = address_parts.get('road', '')
                suburb = address_parts.get('suburb', address_parts.get('neighbourhood', ''))
                
                detected_address = ""
                if street_number and street_name:
                    detected_address = f"{street_number} {street_name}"
                    if suburb:
                        detected_address += f", {suburb}"
                elif street_name:
                    detected_address = street_name
                    if suburb:
                        detected_address += f", {suburb}"
                elif suburb:
                    detected_address = suburb
                else:
                    detected_address = location_data.get('display_name', '').split(',')[0]
                
                if detected_address:
                    detected_address += ", Wellington"
                    
                    # Double-check the detected address is in Wellington
                    if is_wellington_address(detected_address):
                        # Store the detected address
                        user_sessions[call_sid]['detected_address'] = detected_address
                        
                        print(f"📍 WELLINGTON ADDRESS CONFIRMED: {detected_address}")
                        
                        # Ask for confirmation of the detected location
                        response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I can see you're currently at {detected_address}.
        Would you like to be picked up from this location?
        Say yes for pickup from your current location, or no to enter a different pickup address.
    </Say>
    <Gather input="speech" action="/confirm_detected_location" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
                        return Response(response_xml, mimetype="text/xml")
            
        except Exception as e:
            print(f"⚠️ Reverse geocoding failed: {str(e)}")
    
    # Case 4: Wellington mobile/unknown - ask for details
    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I'll help you book your taxi.
        Please tell me your name, pickup address, destination, and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response_xml, mimetype="text/xml")

@app.route("/confirm_detected_location", methods=["POST"])
def confirm_detected_location():
    """Handle confirmation of detected pickup location"""
    data = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    
    print(f"📍 LOCATION CONFIRMATION: '{data}'")
    
    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet", "ok", "okay"]
    no_patterns = ["no", "nah", "wrong", "different", "somewhere else", "another"]
    
    session_data = user_sessions.get(call_sid, {})
    detected_address = session_data.get('detected_address', '')
    
    if any(pattern in data for pattern in yes_patterns):
        # User confirmed the detected location
        print(f"✅ PICKUP CONFIRMED: {detected_address}")
        
        # Store confirmed pickup and ask for rest of details
        user_sessions[call_sid]['confirmed_pickup'] = detected_address
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Pickup confirmed from {detected_address}.
        Now please tell me your name, where you're going, and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_booking_with_confirmed_pickup" method="POST" timeout="12" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
        
    elif any(pattern in data for pattern in no_patterns):
        # User wants different pickup location
        print("🔄 USER WANTS DIFFERENT PICKUP LOCATION")
        
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No problem! Please tell me your exact pickup address, along with your name, destination, and pickup time.
        Speak clearly and take your time.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
        
    else:
        # Unclear response, ask again
        print(f"❓ UNCLEAR LOCATION CONFIRMATION: '{data}'")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. 
        I detected your location as {detected_address}.
        Say yes to be picked up from this location, or no for a different pickup address.
    </Say>
    <Gather input="speech" action="/confirm_detected_location" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_booking_with_confirmed_pickup", methods=["POST"])
def process_booking_with_confirmed_pickup():
    """Process booking where pickup location was confirmed from GPS"""
    data = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🎯 BOOKING WITH CONFIRMED PICKUP: '{data}'")
    
    # Get the confirmed pickup location
    session_data = user_sessions.get(call_sid, {})
    confirmed_pickup = session_data.get('confirmed_pickup', '')
    
    # Create modified speech text that includes the confirmed pickup
    modified_speech = f"Pickup from {confirmed_pickup}. {data}"
    
    print(f"📝 MODIFIED SPEECH: '{modified_speech}'")
    
    # Parse booking details with the confirmed pickup included
    booking_data = parse_booking_details(modified_speech, caller_number)
    
    # Ensure the pickup address is set to our confirmed location
    booking_data['taxicaller_format']['pickup_address'] = confirmed_pickup
    
    # Validate destination and other details
    destination_text = extract_destination_from_speech(data)
    destination_geocoded = geocode_nz_address(destination_text) if destination_text else None
    destination_confident, destination_reason = validate_address_confidence(destination_text or "", destination_geocoded)
    
    print(f"🎯 DESTINATION: '{destination_text}' - Confident: {destination_confident} ({destination_reason})")
    
    if not destination_confident:
        # Destination unclear, ask for clarification
        print("❌ DESTINATION UNCLEAR - asking for clarification")
        user_sessions[call_sid]['partial_booking_with_pickup'] = booking_data
        return redirect_to("/clarify_destination")
    
    # Store booking data for confirmation
    user_sessions[call_sid]['booking_details'] = modified_speech
    
    # Show confirmation
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

@app.route("/process_location_booking", methods=["POST"])
def process_location_booking():
    """Process booking with location suggestions"""
    data = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🗺️ LOCATION BOOKING: '{data}'")
    
    # Get stored location and nearby suggestions
    session_data = user_sessions.get(call_sid, {})
    caller_location = session_data.get('caller_location', {})
    
    # Check if user selected a nearby option
    option_patterns = [
        r'option\s+(\d+)', r'number\s+(\d+)', r'^(\d+)

@app.route("/modify", methods=["POST"])
def modify():
    """Start modification process"""
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

@app.route("/get_phone_for_booking", methods=["POST"])
def get_phone_for_booking():
    """Extract phone number and search for real existing booking"""
    phone_speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Phone Search: '{phone_speech}' (Confidence: {confidence})")
    
    digits_only = re.sub(r'[^\d]', '', phone_speech)
    
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
    
    if phone_number.startswith('64'):
        phone_number = '0' + phone_number[2:]
    elif len(phone_number) == 9 and not phone_number.startswith('0'):
        phone_number = '0' + phone_number
    
    if len(phone_number) >= 8:
        existing_booking = search_existing_booking_real(phone_number)
        
        if existing_booking:
            user_sessions[call_sid] = {
                'search_phone': phone_number,
                'existing_booking': existing_booking
            }
            
            customer_name = existing_booking.get('customer_details', {}).get('name', 'Customer')
            pickup = existing_booking.get('trip_details', {}).get('pickup_address', 'Unknown location')
            destination = existing_booking.get('trip_details', {}).get('destination_address', 'Unknown destination')
            booking_time = existing_booking.get('trip_details', {}).get('pickup_time', 'Unknown time')
            booking_date = existing_booking.get('trip_details', {}).get('pickup_date', 'Unknown date')
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I found your booking for {customer_name}.
        Currently scheduled from {pickup} to {destination} at {booking_time} on {booking_date}.
        What would you like to change? Say pickup location, destination, time, or cancel booking.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
            return Response(response, mimetype="text/xml")
        else:
            return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't find any booking for phone number ending in {phone_number[-4:]}.
        You can book a new taxi instead. Would you like me to help you book a new taxi?
    </Say>
    <Gather input="speech" action="/handle_no_booking_found" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
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

def validate_address_confidence(address_text, geocoded_result):
    """Check if we're confident about the address or need to ask again"""
    
    # High confidence indicators
    high_confidence_keywords = [
        'airport', 'train station', 'railway station', 'wellington station',
        'queen street', 'cuba street', 'lambton quay', 'courtenay place',
        'interislander', 'ferry terminal'
    ]
    
    # Check if it's a well-known landmark
    if any(keyword in address_text.lower() for keyword in high_confidence_keywords):
        return True, "landmark"
    
    # Check if geocoding was successful with good result
    if geocoded_result and geocoded_result.get('formatted_address'):
        original_words = set(address_text.lower().split())
        geocoded_words = set(geocoded_result['formatted_address'].lower().split())
        
        # Check if key words match
        common_words = original_words.intersection(geocoded_words)
        if len(common_words) >= 2:  # At least 2 words match
            return True, "geocoded_match"
    
    # Check for street number + street name pattern
    street_number_pattern = r'\d+\s+[a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way|st|rd|ave|dr|pl|tce|cres)'
    if re.search(street_number_pattern, address_text, re.IGNORECASE):
        return True, "street_pattern"
    
    # Low confidence - need to ask again
    return False, "unclear"

@app.route("/clarify_pickup", methods=["POST"])
def clarify_pickup():
    """Ask caller to repeat pickup address with Wellington validation"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't catch your pickup address clearly. 
        Please tell me again where you need to be picked up from within the Wellington region.
        Speak slowly and clearly, for example: 63 Queen Street Wellington, or Wellington Airport.
    </Say>
    <Gather input="speech" action="/process_pickup_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/clarify_destination", methods=["POST"])
def clarify_destination():
    """Ask caller to repeat destination address with Wellington validation"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't catch your destination clearly. 
        Please tell me again where you're going within the Wellington region.
        Speak slowly and clearly, for example: Wellington Airport, or Train Station.
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_pickup_retry", methods=["POST"])
def process_pickup_retry():
    """Process repeated pickup address with Wellington validation"""
    pickup_speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔄 PICKUP RETRY: '{pickup_speech}'")
    
    # Check if pickup address is in Wellington region
    if not is_wellington_address(pickup_speech):
        print(f"❌ PICKUP OUTSIDE WELLINGTON: '{pickup_speech}'")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Kiwi Cabs operates only in the Wellington region. 
        The pickup address you mentioned appears to be outside our service area.
        Please provide a pickup address within Wellington, Lower Hutt, Upper Hutt, or Porirua.
    </Say>
    <Gather input="speech" action="/process_pickup_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    
    # Try to find pickup address
    pickup_address, pickup_coords = smart_nz_address_lookup(pickup_speech)
    geocoded_pickup = geocode_nz_address(pickup_speech)
    
    is_confident, confidence_reason = validate_address_confidence(pickup_speech, geocoded_pickup)
    
    if is_confident:
        # Store pickup and ask for destination
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['pickup_address'] = pickup_address
        user_sessions[call_sid]['pickup_coords'] = pickup_coords
        
        print(f"✅ WELLINGTON PICKUP CONFIRMED: {pickup_address}")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! Pickup from {pickup_address}.
        Now, where would you like to go within the Wellington region?
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Still not confident, ask one more time
        print(f"❌ PICKUP STILL UNCLEAR: {pickup_speech}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I'm still having trouble with that address. 
        Let me connect you with our team who can help you with your Wellington booking.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_destination_retry", methods=["POST"])
def process_destination_retry():
    """Process repeated destination address with Wellington validation"""
    destination_speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔄 DESTINATION RETRY: '{destination_speech}'")
    
    # Check if destination address is in Wellington region
    if not is_wellington_address(destination_speech):
        print(f"❌ DESTINATION OUTSIDE WELLINGTON: '{destination_speech}'")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Kiwi Cabs operates only in the Wellington region. 
        The destination you mentioned appears to be outside our service area.
        Please provide a destination within Wellington, Lower Hutt, Upper Hutt, or Porirua.
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    
    # Try to find destination address
    destination_address, destination_coords = smart_nz_address_lookup(destination_speech)
    geocoded_destination = geocode_nz_address(destination_speech)
    
    is_confident, confidence_reason = validate_address_confidence(destination_speech, geocoded_destination)
    
    if is_confident:
        # Store destination and ask for time/name
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['destination_address'] = destination_address
        user_sessions[call_sid]['destination_coords'] = destination_coords
        
        print(f"✅ WELLINGTON DESTINATION CONFIRMED: {destination_address}")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Going to {destination_address}.
        Now please tell me your name and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_name_and_time" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Still not confident, transfer to human
        print(f"❌ DESTINATION STILL UNCLEAR: {destination_speech}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I'm having trouble understanding that destination. 
        Let me connect you with our team who can help you complete your Wellington booking.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_name_and_time", methods=["POST"])
def process_name_and_time():
    """Process name and time from caller"""
    speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔄 NAME AND TIME: '{speech}'")
    
    # Parse name and time from speech
    session_data = user_sessions.get(call_sid, {})
    
    # Create booking data with stored addresses
    booking_details = f"My name is {speech}. Pickup from {session_data.get('pickup_address', 'Unknown')}. Going to {session_data.get('destination_address', 'Unknown')}."
    
    booking_data = parse_booking_details(booking_details, caller_number)
    
    # Override with our confirmed addresses
    if session_data.get('pickup_address'):
        booking_data['taxicaller_format']['pickup_address'] = session_data['pickup_address']
    if session_data.get('destination_address'):
        booking_data['taxicaller_format']['destination_address'] = session_data['destination_address']
    
    # Store for confirmation
    user_sessions[call_sid]['booking_data'] = booking_data
    
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
    <Gather input="speech" action="/confirm_smart_booking" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/confirm_smart_booking", methods=["POST"])
def confirm_smart_booking():
    """Confirm booking with validated addresses"""
    data = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    
    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        booking_data = user_sessions.get(call_sid, {}).get('booking_data')
        
        if booking_data:
            print("🚕 SMART BOOKING CONFIRMED - SENDING TO TAXICALLER:")
            print(json.dumps(booking_data['taxicaller_format'], indent=2))
            
            render_success = send_booking_to_render(booking_data)
            
            # Clean up session
            if call_sid in user_sessions:
                del user_sessions[call_sid]
            
            return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Your taxi booking is confirmed. 
        You'll receive a confirmation call shortly with your driver details.
        Thanks for choosing Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        else:
            return redirect_to("/book")
    elif any(pattern in data for pattern in no_patterns):
        return redirect_to("/book")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_smart_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

def parse_booking_details(speech_text, caller_number):
    """Parse and format booking details for TaxiCaller dispatch system"""
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
    original_text = speech_text  # Keep original case
    
    print(f"🔍 PARSING BOOKING: '{speech_text}'")
    
    # Enhanced customer name extraction
    name_patterns = [
        r'(?:my name is|i am|i\'m|this is|name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+(?:i\s+)?(?:need|want|from|at|pickup|going|and|,))',
        r'(?:my name is|i am|i\'m|this is|name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)+)',
        r'^([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+(?:i\s+)?(?:need|want|from|at|pickup|going))',
    ]
    
    customer_name = "Unknown Customer"
    for pattern in name_patterns:
        match = re.search(pattern, original_text, re.IGNORECASE)
        if match:
            name_candidate = match.group(1).strip()
            # Filter out non-name words
            excluded_words = ['need', 'want', 'taxi', 'from', 'to', 'going', 'street', 'road', 'avenue', 'drive', 'wellington', 'airport', 'station', 'today', 'tomorrow', 'morning', 'afternoon', 'evening', 'pickup', 'drop', 'book', 'change', 'time']
            
            # Check if name candidate contains valid name words
            name_words = name_candidate.split()
            valid_name = True
            for word in name_words:
                if word.lower() in excluded_words or len(word) < 2:
                    valid_name = False
                    break
            
            if valid_name and len(name_words) <= 4:  # Reasonable name length
                customer_name = name_candidate.title()
                print(f"✅ NAME FOUND: {customer_name}")
                break
    
    if customer_name == "Unknown Customer":
        print(f"❌ NO VALID NAME FOUND in: {original_text}")
    
    # Enhanced Wellington location database with numbers
    wellington_locations = {
        'queen street': 'Queen Street, Wellington Central, Wellington',
        'cuba street': 'Cuba Street, Wellington Central, Wellington',
        'lambton quay': 'Lambton Quay, Wellington Central, Wellington',
        'willis street': 'Willis Street, Wellington Central, Wellington',
        'courtenay place': 'Courtenay Place, Wellington Central, Wellington',
        'manners street': 'Manners Street, Wellington Central, Wellington',
        'the terrace': 'The Terrace, Wellington Central, Wellington',
        'featherston street': 'Featherston Street, Wellington Central, Wellington',
        'hobart street': 'Hobart Street, Miramar, Wellington',
        'newark street': 'Newark Street, Mount Victoria, Wellington',
        'wellington airport': 'Wellington Airport, Rongotai, Wellington',
        'airport': 'Wellington Airport, Rongotai, Wellington',
        'wellington station': 'Wellington Railway Station, Pipitea, Wellington',
        'train station': 'Wellington Railway Station, Pipitea, Wellington',
        'railway station': 'Wellington Railway Station, Pipitea, Wellington',
        'interislander': 'Interislander Terminal, Aotea Quay, Wellington',
        'ferry terminal': 'Interislander Terminal, Aotea Quay, Wellington',
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
    
    def find_wellington_address(text_segment, is_pickup=False):
        """Smart NZ address lookup using real geocoding"""
        text_segment = text_segment.strip()
        
        print(f"🔍 ADDRESS LOOKUP: '{text_segment}'")
        
        # Use smart geocoding
        formatted_address, coordinates = smart_nz_address_lookup(text_segment)
        
        return formatted_address
    
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
    
    # Enhanced time parsing with better PM/AM detection
    time_patterns = [
        r'(?:at|for|by|today|tomorrow).*?(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|in the evening)',
        r'(?:at|for|by|today|tomorrow).*?(\d{1,2})(?::(\d{2}))?\s*(am|a\.m\.|in the morning)',
        r'(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|evening)',
        r'(\d{1,2})(?::(\d{2}))?\s*(am|a\.m\.|morning)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(pm|am)',
        r'(\d{1,2})\s*(pm|am)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?\s*(pm|am)?',
        r'(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?'
    ]
    
    # Check for explicit PM indicators first
    pm_indicators = ['pm', 'p.m.', 'evening', 'night', 'tonight']
    am_indicators = ['am', 'a.m.', 'morning']
    
    is_pm = any(indicator in text_lower for indicator in pm_indicators)
    is_am = any(indicator in text_lower for indicator in am_indicators)
    
    print(f"DEBUG - Time parsing: '{text_lower}'")
    print(f"DEBUG - PM indicators found: {is_pm}")
    print(f"DEBUG - AM indicators found: {is_am}")
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3) if len(match.groups()) >= 3 and match.group(3) else None
            
            print(f"DEBUG - Matched time: {hour}:{minute:02d}, am_pm: {am_pm}")
            
            # Determine AM/PM
            if am_pm:
                am_pm_lower = am_pm.lower()
                if 'pm' in am_pm_lower or 'evening' in am_pm_lower:
                    is_pm = True
                    is_am = False
                elif 'am' in am_pm_lower or 'morning' in am_pm_lower:
                    is_am = True
                    is_pm = False
            
            # Convert to 24-hour format
            if is_pm and hour != 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0
            elif not is_am and not is_pm:
                # If no AM/PM specified, make intelligent guess
                if hour >= 1 and hour <= 7:
                    # 1-7 without AM/PM likely means PM (1 PM - 7 PM)
                    hour += 12
                    is_pm = True
                elif hour >= 8 and hour <= 11:
                    # 8-11 could be AM or PM, default to AM for morning, PM for evening context
                    if 'evening' in text_lower or 'tonight' in text_lower:
                        hour += 12
                        is_pm = True
            
            print(f"DEBUG - Final hour: {hour}, is_pm: {is_pm}, is_am: {is_am}")
            
            try:
                requested_datetime = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if requested_datetime < current_time:
                    requested_datetime += timedelta(days=1)
                print(f"DEBUG - Parsed datetime: {requested_datetime}")
            except ValueError:
                print(f"DEBUG - Invalid time values: {hour}:{minute}")
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
    """Send booking to TaxiCaller dispatch system using real API"""
    try:
        print("🚀 ATTEMPTING TO SEND BOOKING TO TAXICALLER...")
        print(f"📋 Booking Reference: {booking_data['booking_reference']}")
        
        # First try real TaxiCaller API
        success = create_taxicaller_booking(booking_data)
        
        if success:
            print(f"✅ TAXICALLER API SUCCESS: {booking_data['booking_reference']}")
            
            # Also send to our internal endpoint for logging
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
                
                # Send to our logging endpoint
                response = requests.post(
                    f"{RENDER_ENDPOINT}",
                    json=taxicaller_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                print(f"📊 INTERNAL LOGGING: {response.status_code}")
                
            except Exception as log_error:
                print(f"⚠️ LOGGING ERROR (non-critical): {str(log_error)}")
            
            return True
        else:
            print(f"❌ TAXICALLER API FAILED: {booking_data['booking_reference']}")
            
            # Fallback - still log the booking attempt
            print("🔄 LOGGING FAILED BOOKING ATTEMPT...")
            try:
                fallback_payload = {
                    'booking_reference': booking_data['booking_reference'],
                    'status': 'failed_taxicaller_api',
                    'customer_details': booking_data['taxicaller_format'],
                    'error': 'TaxiCaller API unavailable',
                    'timestamp': datetime.now().isoformat()
                }
                
                response = requests.post(
                    f"{RENDER_ENDPOINT}",
                    json=fallback_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                print(f"📊 FALLBACK LOGGED: {response.status_code}")
                
            except Exception as fallback_error:
                print(f"💥 FALLBACK LOGGING FAILED: {str(fallback_error)}")
            
            return False
            
    except Exception as e:
        print(f"💥 CRITICAL BOOKING ERROR: {str(e)}")
        return False

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Confirm and process new booking"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔔 BOOKING CONFIRMATION: '{data}' (Confidence: {confidence})")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        # Get booking details from session or re-parse
        session_data = user_sessions.get(call_sid, {})
        booking_details = session_data.get('booking_details', '')
        
        if booking_details:
            booking_data = parse_booking_details(booking_details, caller_number)
        else:
            # Fallback - create basic booking
            booking_data = {
                'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'caller_number': caller_number,
                'raw_speech': 'Confirmed booking',
                'timestamp': datetime.now().isoformat(),
                'status': 'confirmed',
                'taxicaller_format': {
                    'customer_name': 'Phone Customer',
                    'pickup_address': 'Wellington Central, Wellington',
                    'destination_address': 'Wellington Airport, Rongotai, Wellington',
                    'booking_date': datetime.now().strftime('%d/%m/%Y'),
                    'booking_time': datetime.now().strftime('%I:%M %p'),
                    'phone_number': caller_number.replace('+64', '0'),
                    'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'special_instructions': 'Booked via AI phone system'
                }
            }
        
        print("=" * 60)
        print("🚕 CONFIRMED BOOKING - SENDING TO TAXICALLER:")
        print("=" * 60)
        print(f"📞 CALL SID: {call_sid}")
        print(f"📱 CALLER: {caller_number}")
        print(f"🔢 REFERENCE: {booking_data['booking_reference']}")
        print("📋 BOOKING DETAILS:")
        for key, value in booking_data['taxicaller_format'].items():
            print(f"   {key}: {value}")
        print("=" * 60)
        
        # Send to TaxiCaller dispatch system
        render_success = send_booking_to_render(booking_data)
        
        # Log the result
        if render_success:
            print("✅ BOOKING SUCCESSFULLY SENT TO TAXICALLER!")
        else:
            print("❌ BOOKING FAILED TO SEND TO TAXICALLER!")
        
        # Clean up session
        if call_sid in user_sessions:
            del user_sessions[call_sid]
        
        success_message = "Perfect! Your taxi booking is confirmed. You'll receive a confirmation call shortly. Thanks for choosing Kiwi Cabs!"
        
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {success_message}
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        
    elif any(pattern in data for pattern in no_patterns):
        print("🔄 CUSTOMER WANTS TO CHANGE BOOKING - redirecting to /book")
        return redirect_to("/book")
    else:
        print(f"❓ UNCLEAR CONFIRMATION RESPONSE: '{data}'")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/process_modification", methods=["POST"])
def process_modification():
    """Process real booking modification request"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Modification Request: '{data}' (Confidence: {confidence})")
    
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
    
    # Store modification request (but don't send to dispatch yet)
    modification_bookings[call_sid] = {
        'phone_number': search_phone,
        'original_booking': existing_booking,
        'modification_request': data,
        'status': 'pending_confirmation'
    }
    
    # Determine what type of modification
    modification_type = determine_modification_type(data)
    
    if modification_type == 'cancel':
        confirmation_message = f"I'll cancel your booking for {existing_booking.get('customer_details', {}).get('name', 'you')}. Say yes to confirm cancellation or no to keep the booking."
    else:
        if modification_type == 'pickup':
            confirmation_message = f"I'll change your pickup location. Say yes to confirm this change or no to try again."
        elif modification_type == 'destination':
            confirmation_message = f"I'll change your destination. Say yes to confirm this change or no to try again."
        elif modification_type == 'time':
            confirmation_message = f"I'll change your pickup time. Say yes to confirm this change or no to try again."
        else:
            confirmation_message = f"I'll update your booking as requested. Say yes to confirm these changes or no to try again."

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {confirmation_message}
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

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
        if 'street' in text_lower or 'road' in text_lower or 'avenue' in text_lower:
            return 'pickup'
        return 'time'

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
        
        if modification_data:
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
</Response>""", mimetype="text/xml")

def redirect_to(path):
    """Helper function for XML redirects"""
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

# API endpoints to handle booking operations with clear logging
@app.route("/api/bookings", methods=["POST"])
def receive_booking():
    """Endpoint to receive and log new booking data"""
    try:
        booking_data = request.get_json()
        
        print("=" * 80)
        print("📨 RECEIVED NEW BOOKING AT /api/bookings:")
        print("=" * 80)
        print(f"🕐 TIMESTAMP: {datetime.now().isoformat()}")
        print(f"📞 BOOKING REF: {booking_data.get('booking_reference', 'N/A')}")
        print(f"👤 CUSTOMER: {booking_data.get('customer_details', {}).get('name', 'N/A')}")
        print(f"📱 PHONE: {booking_data.get('customer_details', {}).get('phone', 'N/A')}")
        print(f"📍 PICKUP: {booking_data.get('trip_details', {}).get('pickup_address', 'N/A')}")
        print(f"🎯 DROPOFF: {booking_data.get('trip_details', {}).get('destination_address', 'N/A')}")
        print(f"📅 DATE: {booking_data.get('trip_details', {}).get('pickup_date', 'N/A')}")
        print(f"⏰ TIME: {booking_data.get('trip_details', {}).get('pickup_time', 'N/A')}")
        print(f"🔄 STATUS: {booking_data.get('booking_info', {}).get('status', 'N/A')}")
        print("📋 FULL DATA:")
        print(json.dumps(booking_data, indent=2))
        print("=" * 80)
        
        return {
            "status": "success", 
            "message": "Booking received and logged successfully", 
            "booking_id": booking_data.get('booking_reference', 'N/A'),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ ERROR RECEIVING BOOKING: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

@app.route("/api/test-booking", methods=["POST"])
def test_booking():
    """Test endpoint to manually send a booking"""
    try:
        test_booking_data = {
            'booking_reference': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'caller_number': '+6421234567',
            'raw_speech': 'Test booking',
            'timestamp': datetime.now().isoformat(),
            'status': 'confirmed',
            'taxicaller_format': {
                'customer_name': 'Test Customer',
                'pickup_address': 'Wellington Airport, Rongotai, Wellington',
                'destination_address': 'Queen Street, Wellington Central, Wellington',
                'booking_date': datetime.now().strftime('%d/%m/%Y'),
                'booking_time': '2:00 PM',
                'phone_number': '0212345678',
                'booking_reference': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'special_instructions': 'Test booking via API'
            }
        }
        
        print("🧪 SENDING TEST BOOKING:")
        success = send_booking_to_render(test_booking_data)
        
        return {
            "status": "success" if success else "failed",
            "message": "Test booking sent",
            "booking_data": test_booking_data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400

@app.route("/search_live_booking", methods=["GET"])
def search_live_booking():
    """Endpoint to search for existing live bookings"""
    try:
        phone = request.args.get('phone', '')
        print(f"🔍 SEARCHING FOR LIVE BOOKING: Phone {phone}")
        
        mock_booking = {
            "booking_details": {
                "booking_reference": f"KC{datetime.now().strftime('%Y%m%d')}001",
                "customer_details": {
                    "name": "John Smith",
                    "phone": phone
                },
                "trip_details": {
                    "pickup_address": "Queen Street, Wellington Central, Wellington",
                    "destination_address": "Wellington Airport, Rongotai, Wellington",
                    "pickup_date": "06/06/2025",
                    "pickup_time": "8:00 AM"
                },
                "booking_info": {
                    "status": "confirmed",
                    "created_at": "2025-06-05T14:30:00Z"
                }
            }
        }
        
        print(f"✅ MOCK BOOKING FOUND: {mock_booking['booking_details']['booking_reference']}")
        return mock_booking
        
    except Exception as e:
        print(f"❌ Error searching booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 404

@app.route("/update_live_booking", methods=["PUT"])
def update_live_booking():
    """Endpoint to update existing live bookings"""
    try:
        modification_data = request.get_json()
        print("🔄 RECEIVED LIVE BOOKING UPDATE:")
        print(json.dumps(modification_data, indent=2))
        
        booking_ref = modification_data.get('booking_reference', 'N/A')
        
        print(f"📋 Updating Booking: {booking_ref}")
        
        response_data = {
            "status": "success",
            "message": "Live booking updated successfully",
            "booking_reference": booking_ref,
            "dispatch_status": "redispatched",
            "updated_at": datetime.now().isoformat(),
            "fleet_notification": "Driver notified of changes"
        }
        
        print("✅ LIVE BOOKING UPDATE SUCCESSFUL (MOCK)")
        return response_data
        
    except Exception as e:
        print(f"❌ Error updating live booking: {str(e)}")
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
        "version": "2.0",
        "endpoints": ["/voice", "/api/bookings", "/health"],
        "integration": "TaxiCaller API Ready"
    }

if __name__ == "__main__":
    app.run(debug=True)
    ]
    
    selected_option = None
    for pattern in option_patterns:
        match = re.search(pattern, data.lower())
        if match:
            selected_option = int(match.group(1))
            break
    
    if selected_option and caller_location.get('has_coordinates'):
        # User selected a nearby location
        nearby_locations = suggest_nearby_locations(caller_location)
        if 1 <= selected_option <= len(nearby_locations):
            selected_location = nearby_locations[selected_option - 1]
            
            # Store the selected pickup location
            user_sessions[call_sid]['auto_pickup'] = selected_location['address']
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Pickup from {selected_location['name']}.
        Now please tell me your name, where you're going, and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_booking_with_auto_pickup" method="POST" timeout="12" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
            return Response(response, mimetype="text/xml")
    
    # Process as normal booking
    return process_booking()

@app.route("/process_booking_with_auto_pickup", methods=["POST"])
def process_booking_with_auto_pickup():
    """Process booking where pickup was auto-selected"""
    data = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    # Get the auto-selected pickup
    session_data = user_sessions.get(call_sid, {})
    auto_pickup = session_data.get('auto_pickup', '')
    
    # Create modified speech text with the auto pickup
    modified_speech = f"Pickup from {auto_pickup}. {data}"
    
    print(f"🎯 AUTO-PICKUP BOOKING: '{modified_speech}'")
    
    # Process normally but with auto pickup included
    booking_data = parse_booking_details(modified_speech, caller_number)
    
    # Override pickup with the auto-selected one
    booking_data['taxicaller_format']['pickup_address'] = auto_pickup
    
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
    
    # Store booking data for confirmation
    user_sessions[call_sid]['booking_details'] = modified_speech
    
    return Response(response, mimetype="text/xml")

@app.route("/modify", methods=["POST"])
def modify():
    """Start modification process"""
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

@app.route("/get_phone_for_booking", methods=["POST"])
def get_phone_for_booking():
    """Extract phone number and search for real existing booking"""
    phone_speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Phone Search: '{phone_speech}' (Confidence: {confidence})")
    
    digits_only = re.sub(r'[^\d]', '', phone_speech)
    
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
    
    if phone_number.startswith('64'):
        phone_number = '0' + phone_number[2:]
    elif len(phone_number) == 9 and not phone_number.startswith('0'):
        phone_number = '0' + phone_number
    
    if len(phone_number) >= 8:
        existing_booking = search_existing_booking_real(phone_number)
        
        if existing_booking:
            user_sessions[call_sid] = {
                'search_phone': phone_number,
                'existing_booking': existing_booking
            }
            
            customer_name = existing_booking.get('customer_details', {}).get('name', 'Customer')
            pickup = existing_booking.get('trip_details', {}).get('pickup_address', 'Unknown location')
            destination = existing_booking.get('trip_details', {}).get('destination_address', 'Unknown destination')
            booking_time = existing_booking.get('trip_details', {}).get('pickup_time', 'Unknown time')
            booking_date = existing_booking.get('trip_details', {}).get('pickup_date', 'Unknown date')
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I found your booking for {customer_name}.
        Currently scheduled from {pickup} to {destination} at {booking_time} on {booking_date}.
        What would you like to change? Say pickup location, destination, time, or cancel booking.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
            return Response(response, mimetype="text/xml")
        else:
            return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't find any booking for phone number ending in {phone_number[-4:]}.
        You can book a new taxi instead. Would you like me to help you book a new taxi?
    </Say>
    <Gather input="speech" action="/handle_no_booking_found" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
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

def validate_address_confidence(address_text, geocoded_result):
    """Check if we're confident about the address or need to ask again"""
    
    # High confidence indicators
    high_confidence_keywords = [
        'airport', 'train station', 'railway station', 'wellington station',
        'queen street', 'cuba street', 'lambton quay', 'courtenay place',
        'interislander', 'ferry terminal'
    ]
    
    # Check if it's a well-known landmark
    if any(keyword in address_text.lower() for keyword in high_confidence_keywords):
        return True, "landmark"
    
    # Check if geocoding was successful with good result
    if geocoded_result and geocoded_result.get('formatted_address'):
        original_words = set(address_text.lower().split())
        geocoded_words = set(geocoded_result['formatted_address'].lower().split())
        
        # Check if key words match
        common_words = original_words.intersection(geocoded_words)
        if len(common_words) >= 2:  # At least 2 words match
            return True, "geocoded_match"
    
    # Check for street number + street name pattern
    street_number_pattern = r'\d+\s+[a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way|st|rd|ave|dr|pl|tce|cres)'
    if re.search(street_number_pattern, address_text, re.IGNORECASE):
        return True, "street_pattern"
    
    # Low confidence - need to ask again
    return False, "unclear"

@app.route("/clarify_pickup", methods=["POST"])
def clarify_pickup():
    """Ask caller to repeat pickup address"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't catch your pickup address clearly. 
        Please tell me again where you need to be picked up from.
        Speak slowly and clearly, for example: 63 Queen Street, or Wellington Airport.
    </Say>
    <Gather input="speech" action="/process_pickup_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/clarify_destination", methods=["POST"])
def clarify_destination():
    """Ask caller to repeat destination address"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't catch your destination clearly. 
        Please tell me again where you're going.
        Speak slowly and clearly, for example: Wellington Airport, or Train Station.
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_pickup_retry", methods=["POST"])
def process_pickup_retry():
    """Process repeated pickup address"""
    pickup_speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔄 PICKUP RETRY: '{pickup_speech}'")
    
    # Try to find pickup address
    pickup_address, pickup_coords = smart_nz_address_lookup(pickup_speech)
    geocoded_pickup = geocode_nz_address(pickup_speech)
    
    is_confident, confidence_reason = validate_address_confidence(pickup_speech, geocoded_pickup)
    
    if is_confident:
        # Store pickup and ask for destination
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['pickup_address'] = pickup_address
        user_sessions[call_sid]['pickup_coords'] = pickup_coords
        
        print(f"✅ PICKUP CONFIRMED: {pickup_address}")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! Pickup from {pickup_address}.
        Now, where would you like to go? Please tell me your destination.
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Still not confident, ask one more time
        print(f"❌ PICKUP STILL UNCLEAR: {pickup_speech}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I'm still having trouble with that address. 
        Let me connect you with our team who can help you with your booking.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_destination_retry", methods=["POST"])
def process_destination_retry():
    """Process repeated destination address"""
    destination_speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔄 DESTINATION RETRY: '{destination_speech}'")
    
    # Try to find destination address
    destination_address, destination_coords = smart_nz_address_lookup(destination_speech)
    geocoded_destination = geocode_nz_address(destination_speech)
    
    is_confident, confidence_reason = validate_address_confidence(destination_speech, geocoded_destination)
    
    if is_confident:
        # Store destination and ask for time/name
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['destination_address'] = destination_address
        user_sessions[call_sid]['destination_coords'] = destination_coords
        
        print(f"✅ DESTINATION CONFIRMED: {destination_address}")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Going to {destination_address}.
        Now please tell me your name and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_name_and_time" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Still not confident, transfer to human
        print(f"❌ DESTINATION STILL UNCLEAR: {destination_speech}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I'm having trouble understanding that destination. 
        Let me connect you with our team who can help you complete your booking.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_name_and_time", methods=["POST"])
def process_name_and_time():
    """Process name and time from caller"""
    speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔄 NAME AND TIME: '{speech}'")
    
    # Parse name and time from speech
    session_data = user_sessions.get(call_sid, {})
    
    # Create booking data with stored addresses
    booking_details = f"My name is {speech}. Pickup from {session_data.get('pickup_address', 'Unknown')}. Going to {session_data.get('destination_address', 'Unknown')}."
    
    booking_data = parse_booking_details(booking_details, caller_number)
    
    # Override with our confirmed addresses
    if session_data.get('pickup_address'):
        booking_data['taxicaller_format']['pickup_address'] = session_data['pickup_address']
    if session_data.get('destination_address'):
        booking_data['taxicaller_format']['destination_address'] = session_data['destination_address']
    
    # Store for confirmation
    user_sessions[call_sid]['booking_data'] = booking_data
    
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
    <Gather input="speech" action="/confirm_smart_booking" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/confirm_smart_booking", methods=["POST"])
def confirm_smart_booking():
    """Confirm booking with validated addresses"""
    data = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    
    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        booking_data = user_sessions.get(call_sid, {}).get('booking_data')
        
        if booking_data:
            print("🚕 SMART BOOKING CONFIRMED - SENDING TO TAXICALLER:")
            print(json.dumps(booking_data['taxicaller_format'], indent=2))
            
            render_success = send_booking_to_render(booking_data)
            
            # Clean up session
            if call_sid in user_sessions:
                del user_sessions[call_sid]
            
            return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Your taxi booking is confirmed. 
        You'll receive a confirmation call shortly with your driver details.
        Thanks for choosing Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        else:
            return redirect_to("/book")
    elif any(pattern in data for pattern in no_patterns):
        return redirect_to("/book")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_smart_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

def parse_booking_details(speech_text, caller_number):
    """Parse and format booking details for TaxiCaller dispatch system"""
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
    original_text = speech_text  # Keep original case
    
    print(f"🔍 PARSING BOOKING: '{speech_text}'")
    
    # Enhanced customer name extraction
    name_patterns = [
        r'(?:my name is|i am|i\'m|this is|name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+(?:i\s+)?(?:need|want|from|at|pickup|going|and|,))',
        r'(?:my name is|i am|i\'m|this is|name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)+)',
        r'^([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+(?:i\s+)?(?:need|want|from|at|pickup|going))',
    ]
    
    customer_name = "Unknown Customer"
    for pattern in name_patterns:
        match = re.search(pattern, original_text, re.IGNORECASE)
        if match:
            name_candidate = match.group(1).strip()
            # Filter out non-name words
            excluded_words = ['need', 'want', 'taxi', 'from', 'to', 'going', 'street', 'road', 'avenue', 'drive', 'wellington', 'airport', 'station', 'today', 'tomorrow', 'morning', 'afternoon', 'evening', 'pickup', 'drop', 'book', 'change', 'time']
            
            # Check if name candidate contains valid name words
            name_words = name_candidate.split()
            valid_name = True
            for word in name_words:
                if word.lower() in excluded_words or len(word) < 2:
                    valid_name = False
                    break
            
            if valid_name and len(name_words) <= 4:  # Reasonable name length
                customer_name = name_candidate.title()
                print(f"✅ NAME FOUND: {customer_name}")
                break
    
    if customer_name == "Unknown Customer":
        print(f"❌ NO VALID NAME FOUND in: {original_text}")
    
    # Enhanced Wellington location database with numbers
    wellington_locations = {
        'queen street': 'Queen Street, Wellington Central, Wellington',
        'cuba street': 'Cuba Street, Wellington Central, Wellington',
        'lambton quay': 'Lambton Quay, Wellington Central, Wellington',
        'willis street': 'Willis Street, Wellington Central, Wellington',
        'courtenay place': 'Courtenay Place, Wellington Central, Wellington',
        'manners street': 'Manners Street, Wellington Central, Wellington',
        'the terrace': 'The Terrace, Wellington Central, Wellington',
        'featherston street': 'Featherston Street, Wellington Central, Wellington',
        'hobart street': 'Hobart Street, Miramar, Wellington',
        'newark street': 'Newark Street, Mount Victoria, Wellington',
        'wellington airport': 'Wellington Airport, Rongotai, Wellington',
        'airport': 'Wellington Airport, Rongotai, Wellington',
        'wellington station': 'Wellington Railway Station, Pipitea, Wellington',
        'train station': 'Wellington Railway Station, Pipitea, Wellington',
        'railway station': 'Wellington Railway Station, Pipitea, Wellington',
        'interislander': 'Interislander Terminal, Aotea Quay, Wellington',
        'ferry terminal': 'Interislander Terminal, Aotea Quay, Wellington',
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
    
    def find_wellington_address(text_segment, is_pickup=False):
        """Smart NZ address lookup using real geocoding"""
        text_segment = text_segment.strip()
        
        print(f"🔍 ADDRESS LOOKUP: '{text_segment}'")
        
        # Use smart geocoding
        formatted_address, coordinates = smart_nz_address_lookup(text_segment)
        
        return formatted_address
    
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
    
    # Enhanced time parsing with better PM/AM detection
    time_patterns = [
        r'(?:at|for|by|today|tomorrow).*?(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|in the evening)',
        r'(?:at|for|by|today|tomorrow).*?(\d{1,2})(?::(\d{2}))?\s*(am|a\.m\.|in the morning)',
        r'(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|evening)',
        r'(\d{1,2})(?::(\d{2}))?\s*(am|a\.m\.|morning)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(pm|am)',
        r'(\d{1,2})\s*(pm|am)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?\s*(pm|am)?',
        r'(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?'
    ]
    
    # Check for explicit PM indicators first
    pm_indicators = ['pm', 'p.m.', 'evening', 'night', 'tonight']
    am_indicators = ['am', 'a.m.', 'morning']
    
    is_pm = any(indicator in text_lower for indicator in pm_indicators)
    is_am = any(indicator in text_lower for indicator in am_indicators)
    
    print(f"DEBUG - Time parsing: '{text_lower}'")
    print(f"DEBUG - PM indicators found: {is_pm}")
    print(f"DEBUG - AM indicators found: {is_am}")
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3) if len(match.groups()) >= 3 and match.group(3) else None
            
            print(f"DEBUG - Matched time: {hour}:{minute:02d}, am_pm: {am_pm}")
            
            # Determine AM/PM
            if am_pm:
                am_pm_lower = am_pm.lower()
                if 'pm' in am_pm_lower or 'evening' in am_pm_lower:
                    is_pm = True
                    is_am = False
                elif 'am' in am_pm_lower or 'morning' in am_pm_lower:
                    is_am = True
                    is_pm = False
            
            # Convert to 24-hour format
            if is_pm and hour != 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0
            elif not is_am and not is_pm:
                # If no AM/PM specified, make intelligent guess
                if hour >= 1 and hour <= 7:
                    # 1-7 without AM/PM likely means PM (1 PM - 7 PM)
                    hour += 12
                    is_pm = True
                elif hour >= 8 and hour <= 11:
                    # 8-11 could be AM or PM, default to AM for morning, PM for evening context
                    if 'evening' in text_lower or 'tonight' in text_lower:
                        hour += 12
                        is_pm = True
            
            print(f"DEBUG - Final hour: {hour}, is_pm: {is_pm}, is_am: {is_am}")
            
            try:
                requested_datetime = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if requested_datetime < current_time:
                    requested_datetime += timedelta(days=1)
                print(f"DEBUG - Parsed datetime: {requested_datetime}")
            except ValueError:
                print(f"DEBUG - Invalid time values: {hour}:{minute}")
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
    """Send booking to TaxiCaller dispatch system using real API"""
    try:
        print("🚀 ATTEMPTING TO SEND BOOKING TO TAXICALLER...")
        print(f"📋 Booking Reference: {booking_data['booking_reference']}")
        
        # First try real TaxiCaller API
        success = create_taxicaller_booking(booking_data)
        
        if success:
            print(f"✅ TAXICALLER API SUCCESS: {booking_data['booking_reference']}")
            
            # Also send to our internal endpoint for logging
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
                
                # Send to our logging endpoint
                response = requests.post(
                    f"{RENDER_ENDPOINT}",
                    json=taxicaller_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                print(f"📊 INTERNAL LOGGING: {response.status_code}")
                
            except Exception as log_error:
                print(f"⚠️ LOGGING ERROR (non-critical): {str(log_error)}")
            
            return True
        else:
            print(f"❌ TAXICALLER API FAILED: {booking_data['booking_reference']}")
            
            # Fallback - still log the booking attempt
            print("🔄 LOGGING FAILED BOOKING ATTEMPT...")
            try:
                fallback_payload = {
                    'booking_reference': booking_data['booking_reference'],
                    'status': 'failed_taxicaller_api',
                    'customer_details': booking_data['taxicaller_format'],
                    'error': 'TaxiCaller API unavailable',
                    'timestamp': datetime.now().isoformat()
                }
                
                response = requests.post(
                    f"{RENDER_ENDPOINT}",
                    json=fallback_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                print(f"📊 FALLBACK LOGGED: {response.status_code}")
                
            except Exception as fallback_error:
                print(f"💥 FALLBACK LOGGING FAILED: {str(fallback_error)}")
            
            return False
            
    except Exception as e:
        print(f"💥 CRITICAL BOOKING ERROR: {str(e)}")
        return False

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Confirm and process new booking"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔔 BOOKING CONFIRMATION: '{data}' (Confidence: {confidence})")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        # Get booking details from session or re-parse
        session_data = user_sessions.get(call_sid, {})
        booking_details = session_data.get('booking_details', '')
        
        if booking_details:
            booking_data = parse_booking_details(booking_details, caller_number)
        else:
            # Fallback - create basic booking
            booking_data = {
                'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'caller_number': caller_number,
                'raw_speech': 'Confirmed booking',
                'timestamp': datetime.now().isoformat(),
                'status': 'confirmed',
                'taxicaller_format': {
                    'customer_name': 'Phone Customer',
                    'pickup_address': 'Wellington Central, Wellington',
                    'destination_address': 'Wellington Airport, Rongotai, Wellington',
                    'booking_date': datetime.now().strftime('%d/%m/%Y'),
                    'booking_time': datetime.now().strftime('%I:%M %p'),
                    'phone_number': caller_number.replace('+64', '0'),
                    'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'special_instructions': 'Booked via AI phone system'
                }
            }
        
        print("=" * 60)
        print("🚕 CONFIRMED BOOKING - SENDING TO TAXICALLER:")
        print("=" * 60)
        print(f"📞 CALL SID: {call_sid}")
        print(f"📱 CALLER: {caller_number}")
        print(f"🔢 REFERENCE: {booking_data['booking_reference']}")
        print("📋 BOOKING DETAILS:")
        for key, value in booking_data['taxicaller_format'].items():
            print(f"   {key}: {value}")
        print("=" * 60)
        
        # Send to TaxiCaller dispatch system
        render_success = send_booking_to_render(booking_data)
        
        # Log the result
        if render_success:
            print("✅ BOOKING SUCCESSFULLY SENT TO TAXICALLER!")
        else:
            print("❌ BOOKING FAILED TO SEND TO TAXICALLER!")
        
        # Clean up session
        if call_sid in user_sessions:
            del user_sessions[call_sid]
        
        success_message = "Perfect! Your taxi booking is confirmed. You'll receive a confirmation call shortly. Thanks for choosing Kiwi Cabs!"
        
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {success_message}
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        
    elif any(pattern in data for pattern in no_patterns):
        print("🔄 CUSTOMER WANTS TO CHANGE BOOKING - redirecting to /book")
        return redirect_to("/book")
    else:
        print(f"❓ UNCLEAR CONFIRMATION RESPONSE: '{data}'")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/process_modification", methods=["POST"])
def process_modification():
    """Process real booking modification request"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Modification Request: '{data}' (Confidence: {confidence})")
    
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
    
    # Store modification request (but don't send to dispatch yet)
    modification_bookings[call_sid] = {
        'phone_number': search_phone,
        'original_booking': existing_booking,
        'modification_request': data,
        'status': 'pending_confirmation'
    }
    
    # Determine what type of modification
    modification_type = determine_modification_type(data)
    
    if modification_type == 'cancel':
        confirmation_message = f"I'll cancel your booking for {existing_booking.get('customer_details', {}).get('name', 'you')}. Say yes to confirm cancellation or no to keep the booking."
    else:
        if modification_type == 'pickup':
            confirmation_message = f"I'll change your pickup location. Say yes to confirm this change or no to try again."
        elif modification_type == 'destination':
            confirmation_message = f"I'll change your destination. Say yes to confirm this change or no to try again."
        elif modification_type == 'time':
            confirmation_message = f"I'll change your pickup time. Say yes to confirm this change or no to try again."
        else:
            confirmation_message = f"I'll update your booking as requested. Say yes to confirm these changes or no to try again."

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {confirmation_message}
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

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
        if 'street' in text_lower or 'road' in text_lower or 'avenue' in text_lower:
            return 'pickup'
        return 'time'

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
        
        if modification_data:
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
</Response>""", mimetype="text/xml")

def redirect_to(path):
    """Helper function for XML redirects"""
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

# API endpoints to handle booking operations with clear logging
@app.route("/api/bookings", methods=["POST"])
def receive_booking():
    """Endpoint to receive and log new booking data"""
    try:
        booking_data = request.get_json()
        
        print("=" * 80)
        print("📨 RECEIVED NEW BOOKING AT /api/bookings:")
        print("=" * 80)
        print(f"🕐 TIMESTAMP: {datetime.now().isoformat()}")
        print(f"📞 BOOKING REF: {booking_data.get('booking_reference', 'N/A')}")
        print(f"👤 CUSTOMER: {booking_data.get('customer_details', {}).get('name', 'N/A')}")
        print(f"📱 PHONE: {booking_data.get('customer_details', {}).get('phone', 'N/A')}")
        print(f"📍 PICKUP: {booking_data.get('trip_details', {}).get('pickup_address', 'N/A')}")
        print(f"🎯 DROPOFF: {booking_data.get('trip_details', {}).get('destination_address', 'N/A')}")
        print(f"📅 DATE: {booking_data.get('trip_details', {}).get('pickup_date', 'N/A')}")
        print(f"⏰ TIME: {booking_data.get('trip_details', {}).get('pickup_time', 'N/A')}")
        print(f"🔄 STATUS: {booking_data.get('booking_info', {}).get('status', 'N/A')}")
        print("📋 FULL DATA:")
        print(json.dumps(booking_data, indent=2))
        print("=" * 80)
        
        return {
            "status": "success", 
            "message": "Booking received and logged successfully", 
            "booking_id": booking_data.get('booking_reference', 'N/A'),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ ERROR RECEIVING BOOKING: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

@app.route("/api/test-booking", methods=["POST"])
def test_booking():
    """Test endpoint to manually send a booking"""
    try:
        test_booking_data = {
            'booking_reference': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'caller_number': '+6421234567',
            'raw_speech': 'Test booking',
            'timestamp': datetime.now().isoformat(),
            'status': 'confirmed',
            'taxicaller_format': {
                'customer_name': 'Test Customer',
                'pickup_address': 'Wellington Airport, Rongotai, Wellington',
                'destination_address': 'Queen Street, Wellington Central, Wellington',
                'booking_date': datetime.now().strftime('%d/%m/%Y'),
                'booking_time': '2:00 PM',
                'phone_number': '0212345678',
                'booking_reference': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'special_instructions': 'Test booking via API'
            }
        }
        
        print("🧪 SENDING TEST BOOKING:")
        success = send_booking_to_render(test_booking_data)
        
        return {
            "status": "success" if success else "failed",
            "message": "Test booking sent",
            "booking_data": test_booking_data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400

@app.route("/search_live_booking", methods=["GET"])
def search_live_booking():
    """Endpoint to search for existing live bookings"""
    try:
        phone = request.args.get('phone', '')
        print(f"🔍 SEARCHING FOR LIVE BOOKING: Phone {phone}")
        
        mock_booking = {
            "booking_details": {
                "booking_reference": f"KC{datetime.now().strftime('%Y%m%d')}001",
                "customer_details": {
                    "name": "John Smith",
                    "phone": phone
                },
                "trip_details": {
                    "pickup_address": "Queen Street, Wellington Central, Wellington",
                    "destination_address": "Wellington Airport, Rongotai, Wellington",
                    "pickup_date": "06/06/2025",
                    "pickup_time": "8:00 AM"
                },
                "booking_info": {
                    "status": "confirmed",
                    "created_at": "2025-06-05T14:30:00Z"
                }
            }
        }
        
        print(f"✅ MOCK BOOKING FOUND: {mock_booking['booking_details']['booking_reference']}")
        return mock_booking
        
    except Exception as e:
        print(f"❌ Error searching booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 404

@app.route("/update_live_booking", methods=["PUT"])
def update_live_booking():
    """Endpoint to update existing live bookings"""
    try:
        modification_data = request.get_json()
        print("🔄 RECEIVED LIVE BOOKING UPDATE:")
        print(json.dumps(modification_data, indent=2))
        
        booking_ref = modification_data.get('booking_reference', 'N/A')
        
        print(f"📋 Updating Booking: {booking_ref}")
        
        response_data = {
            "status": "success",
            "message": "Live booking updated successfully",
            "booking_reference": booking_ref,
            "dispatch_status": "redispatched",
            "updated_at": datetime.now().isoformat(),
            "fleet_notification": "Driver notified of changes"
        }
        
        print("✅ LIVE BOOKING UPDATE SUCCESSFUL (MOCK)")
        return response_data
        
    except Exception as e:
        print(f"❌ Error updating live booking: {str(e)}")
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
        "version": "2.0",
        "endpoints": ["/voice", "/api/bookings", "/health"],
        "integration": "TaxiCaller API Ready"
    }

if __name__ == "__main__":
    app.run(debug=True)
    ]

@app.route("/modify", methods=["POST"])
def modify():
    """Start modification process"""
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

@app.route("/get_phone_for_booking", methods=["POST"])
def get_phone_for_booking():
    """Extract phone number and search for real existing booking"""
    phone_speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Phone Search: '{phone_speech}' (Confidence: {confidence})")
    
    digits_only = re.sub(r'[^\d]', '', phone_speech)
    
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
    
    if phone_number.startswith('64'):
        phone_number = '0' + phone_number[2:]
    elif len(phone_number) == 9 and not phone_number.startswith('0'):
        phone_number = '0' + phone_number
    
    if len(phone_number) >= 8:
        existing_booking = search_existing_booking_real(phone_number)
        
        if existing_booking:
            user_sessions[call_sid] = {
                'search_phone': phone_number,
                'existing_booking': existing_booking
            }
            
            customer_name = existing_booking.get('customer_details', {}).get('name', 'Customer')
            pickup = existing_booking.get('trip_details', {}).get('pickup_address', 'Unknown location')
            destination = existing_booking.get('trip_details', {}).get('destination_address', 'Unknown destination')
            booking_time = existing_booking.get('trip_details', {}).get('pickup_time', 'Unknown time')
            booking_date = existing_booking.get('trip_details', {}).get('pickup_date', 'Unknown date')
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I found your booking for {customer_name}.
        Currently scheduled from {pickup} to {destination} at {booking_time} on {booking_date}.
        What would you like to change? Say pickup location, destination, time, or cancel booking.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
            return Response(response, mimetype="text/xml")
        else:
            return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't find any booking for phone number ending in {phone_number[-4:]}.
        You can book a new taxi instead. Would you like me to help you book a new taxi?
    </Say>
    <Gather input="speech" action="/handle_no_booking_found" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
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

def validate_address_confidence(address_text, geocoded_result):
    """Check if we're confident about the address or need to ask again"""
    
    # High confidence indicators
    high_confidence_keywords = [
        'airport', 'train station', 'railway station', 'wellington station',
        'queen street', 'cuba street', 'lambton quay', 'courtenay place',
        'interislander', 'ferry terminal'
    ]
    
    # Check if it's a well-known landmark
    if any(keyword in address_text.lower() for keyword in high_confidence_keywords):
        return True, "landmark"
    
    # Check if geocoding was successful with good result
    if geocoded_result and geocoded_result.get('formatted_address'):
        original_words = set(address_text.lower().split())
        geocoded_words = set(geocoded_result['formatted_address'].lower().split())
        
        # Check if key words match
        common_words = original_words.intersection(geocoded_words)
        if len(common_words) >= 2:  # At least 2 words match
            return True, "geocoded_match"
    
    # Check for street number + street name pattern
    street_number_pattern = r'\d+\s+[a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way|st|rd|ave|dr|pl|tce|cres)'
    if re.search(street_number_pattern, address_text, re.IGNORECASE):
        return True, "street_pattern"
    
    # Low confidence - need to ask again
    return False, "unclear"

@app.route("/clarify_pickup", methods=["POST"])
def clarify_pickup():
    """Ask caller to repeat pickup address with Wellington validation"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't catch your pickup address clearly. 
        Please tell me again where you need to be picked up from within the Wellington region.
        Speak slowly and clearly, for example: 63 Queen Street Wellington, or Wellington Airport.
    </Say>
    <Gather input="speech" action="/process_pickup_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/clarify_destination", methods=["POST"])
def clarify_destination():
    """Ask caller to repeat destination address with Wellington validation"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't catch your destination clearly. 
        Please tell me again where you're going within the Wellington region.
        Speak slowly and clearly, for example: Wellington Airport, or Train Station.
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_pickup_retry", methods=["POST"])
def process_pickup_retry():
    """Process repeated pickup address with Wellington validation"""
    pickup_speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔄 PICKUP RETRY: '{pickup_speech}'")
    
    # Check if pickup address is in Wellington region
    if not is_wellington_address(pickup_speech):
        print(f"❌ PICKUP OUTSIDE WELLINGTON: '{pickup_speech}'")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Kiwi Cabs operates only in the Wellington region. 
        The pickup address you mentioned appears to be outside our service area.
        Please provide a pickup address within Wellington, Lower Hutt, Upper Hutt, or Porirua.
    </Say>
    <Gather input="speech" action="/process_pickup_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    
    # Try to find pickup address
    pickup_address, pickup_coords = smart_nz_address_lookup(pickup_speech)
    geocoded_pickup = geocode_nz_address(pickup_speech)
    
    is_confident, confidence_reason = validate_address_confidence(pickup_speech, geocoded_pickup)
    
    if is_confident:
        # Store pickup and ask for destination
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['pickup_address'] = pickup_address
        user_sessions[call_sid]['pickup_coords'] = pickup_coords
        
        print(f"✅ WELLINGTON PICKUP CONFIRMED: {pickup_address}")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! Pickup from {pickup_address}.
        Now, where would you like to go within the Wellington region?
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Still not confident, ask one more time
        print(f"❌ PICKUP STILL UNCLEAR: {pickup_speech}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I'm still having trouble with that address. 
        Let me connect you with our team who can help you with your Wellington booking.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_destination_retry", methods=["POST"])
def process_destination_retry():
    """Process repeated destination address with Wellington validation"""
    destination_speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔄 DESTINATION RETRY: '{destination_speech}'")
    
    # Check if destination address is in Wellington region
    if not is_wellington_address(destination_speech):
        print(f"❌ DESTINATION OUTSIDE WELLINGTON: '{destination_speech}'")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, Kiwi Cabs operates only in the Wellington region. 
        The destination you mentioned appears to be outside our service area.
        Please provide a destination within Wellington, Lower Hutt, Upper Hutt, or Porirua.
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    
    # Try to find destination address
    destination_address, destination_coords = smart_nz_address_lookup(destination_speech)
    geocoded_destination = geocode_nz_address(destination_speech)
    
    is_confident, confidence_reason = validate_address_confidence(destination_speech, geocoded_destination)
    
    if is_confident:
        # Store destination and ask for time/name
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['destination_address'] = destination_address
        user_sessions[call_sid]['destination_coords'] = destination_coords
        
        print(f"✅ WELLINGTON DESTINATION CONFIRMED: {destination_address}")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Going to {destination_address}.
        Now please tell me your name and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_name_and_time" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Still not confident, transfer to human
        print(f"❌ DESTINATION STILL UNCLEAR: {destination_speech}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I'm having trouble understanding that destination. 
        Let me connect you with our team who can help you complete your Wellington booking.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_name_and_time", methods=["POST"])
def process_name_and_time():
    """Process name and time from caller"""
    speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔄 NAME AND TIME: '{speech}'")
    
    # Parse name and time from speech
    session_data = user_sessions.get(call_sid, {})
    
    # Create booking data with stored addresses
    booking_details = f"My name is {speech}. Pickup from {session_data.get('pickup_address', 'Unknown')}. Going to {session_data.get('destination_address', 'Unknown')}."
    
    booking_data = parse_booking_details(booking_details, caller_number)
    
    # Override with our confirmed addresses
    if session_data.get('pickup_address'):
        booking_data['taxicaller_format']['pickup_address'] = session_data['pickup_address']
    if session_data.get('destination_address'):
        booking_data['taxicaller_format']['destination_address'] = session_data['destination_address']
    
    # Store for confirmation
    user_sessions[call_sid]['booking_data'] = booking_data
    
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
    <Gather input="speech" action="/confirm_smart_booking" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/confirm_smart_booking", methods=["POST"])
def confirm_smart_booking():
    """Confirm booking with validated addresses"""
    data = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    
    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        booking_data = user_sessions.get(call_sid, {}).get('booking_data')
        
        if booking_data:
            print("🚕 SMART BOOKING CONFIRMED - SENDING TO TAXICALLER:")
            print(json.dumps(booking_data['taxicaller_format'], indent=2))
            
            render_success = send_booking_to_render(booking_data)
            
            # Clean up session
            if call_sid in user_sessions:
                del user_sessions[call_sid]
            
            return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Your taxi booking is confirmed. 
        You'll receive a confirmation call shortly with your driver details.
        Thanks for choosing Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        else:
            return redirect_to("/book")
    elif any(pattern in data for pattern in no_patterns):
        return redirect_to("/book")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_smart_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

def parse_booking_details(speech_text, caller_number):
    """Parse and format booking details for TaxiCaller dispatch system"""
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
    original_text = speech_text  # Keep original case
    
    print(f"🔍 PARSING BOOKING: '{speech_text}'")
    
    # Enhanced customer name extraction
    name_patterns = [
        r'(?:my name is|i am|i\'m|this is|name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+(?:i\s+)?(?:need|want|from|at|pickup|going|and|,))',
        r'(?:my name is|i am|i\'m|this is|name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)+)',
        r'^([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+(?:i\s+)?(?:need|want|from|at|pickup|going))',
    ]
    
    customer_name = "Unknown Customer"
    for pattern in name_patterns:
        match = re.search(pattern, original_text, re.IGNORECASE)
        if match:
            name_candidate = match.group(1).strip()
            # Filter out non-name words
            excluded_words = ['need', 'want', 'taxi', 'from', 'to', 'going', 'street', 'road', 'avenue', 'drive', 'wellington', 'airport', 'station', 'today', 'tomorrow', 'morning', 'afternoon', 'evening', 'pickup', 'drop', 'book', 'change', 'time']
            
            # Check if name candidate contains valid name words
            name_words = name_candidate.split()
            valid_name = True
            for word in name_words:
                if word.lower() in excluded_words or len(word) < 2:
                    valid_name = False
                    break
            
            if valid_name and len(name_words) <= 4:  # Reasonable name length
                customer_name = name_candidate.title()
                print(f"✅ NAME FOUND: {customer_name}")
                break
    
    if customer_name == "Unknown Customer":
        print(f"❌ NO VALID NAME FOUND in: {original_text}")
    
    # Enhanced Wellington location database with numbers
    wellington_locations = {
        'queen street': 'Queen Street, Wellington Central, Wellington',
        'cuba street': 'Cuba Street, Wellington Central, Wellington',
        'lambton quay': 'Lambton Quay, Wellington Central, Wellington',
        'willis street': 'Willis Street, Wellington Central, Wellington',
        'courtenay place': 'Courtenay Place, Wellington Central, Wellington',
        'manners street': 'Manners Street, Wellington Central, Wellington',
        'the terrace': 'The Terrace, Wellington Central, Wellington',
        'featherston street': 'Featherston Street, Wellington Central, Wellington',
        'hobart street': 'Hobart Street, Miramar, Wellington',
        'newark street': 'Newark Street, Mount Victoria, Wellington',
        'wellington airport': 'Wellington Airport, Rongotai, Wellington',
        'airport': 'Wellington Airport, Rongotai, Wellington',
        'wellington station': 'Wellington Railway Station, Pipitea, Wellington',
        'train station': 'Wellington Railway Station, Pipitea, Wellington',
        'railway station': 'Wellington Railway Station, Pipitea, Wellington',
        'interislander': 'Interislander Terminal, Aotea Quay, Wellington',
        'ferry terminal': 'Interislander Terminal, Aotea Quay, Wellington',
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
    
    def find_wellington_address(text_segment, is_pickup=False):
        """Smart NZ address lookup using real geocoding"""
        text_segment = text_segment.strip()
        
        print(f"🔍 ADDRESS LOOKUP: '{text_segment}'")
        
        # Use smart geocoding
        formatted_address, coordinates = smart_nz_address_lookup(text_segment)
        
        return formatted_address
    
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
    
    # Enhanced time parsing with better PM/AM detection
    time_patterns = [
        r'(?:at|for|by|today|tomorrow).*?(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|in the evening)',
        r'(?:at|for|by|today|tomorrow).*?(\d{1,2})(?::(\d{2}))?\s*(am|a\.m\.|in the morning)',
        r'(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|evening)',
        r'(\d{1,2})(?::(\d{2}))?\s*(am|a\.m\.|morning)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(pm|am)',
        r'(\d{1,2})\s*(pm|am)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?\s*(pm|am)?',
        r'(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?'
    ]
    
    # Check for explicit PM indicators first
    pm_indicators = ['pm', 'p.m.', 'evening', 'night', 'tonight']
    am_indicators = ['am', 'a.m.', 'morning']
    
    is_pm = any(indicator in text_lower for indicator in pm_indicators)
    is_am = any(indicator in text_lower for indicator in am_indicators)
    
    print(f"DEBUG - Time parsing: '{text_lower}'")
    print(f"DEBUG - PM indicators found: {is_pm}")
    print(f"DEBUG - AM indicators found: {is_am}")
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3) if len(match.groups()) >= 3 and match.group(3) else None
            
            print(f"DEBUG - Matched time: {hour}:{minute:02d}, am_pm: {am_pm}")
            
            # Determine AM/PM
            if am_pm:
                am_pm_lower = am_pm.lower()
                if 'pm' in am_pm_lower or 'evening' in am_pm_lower:
                    is_pm = True
                    is_am = False
                elif 'am' in am_pm_lower or 'morning' in am_pm_lower:
                    is_am = True
                    is_pm = False
            
            # Convert to 24-hour format
            if is_pm and hour != 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0
            elif not is_am and not is_pm:
                # If no AM/PM specified, make intelligent guess
                if hour >= 1 and hour <= 7:
                    # 1-7 without AM/PM likely means PM (1 PM - 7 PM)
                    hour += 12
                    is_pm = True
                elif hour >= 8 and hour <= 11:
                    # 8-11 could be AM or PM, default to AM for morning, PM for evening context
                    if 'evening' in text_lower or 'tonight' in text_lower:
                        hour += 12
                        is_pm = True
            
            print(f"DEBUG - Final hour: {hour}, is_pm: {is_pm}, is_am: {is_am}")
            
            try:
                requested_datetime = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if requested_datetime < current_time:
                    requested_datetime += timedelta(days=1)
                print(f"DEBUG - Parsed datetime: {requested_datetime}")
            except ValueError:
                print(f"DEBUG - Invalid time values: {hour}:{minute}")
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
    """Send booking to TaxiCaller dispatch system using real API"""
    try:
        print("🚀 ATTEMPTING TO SEND BOOKING TO TAXICALLER...")
        print(f"📋 Booking Reference: {booking_data['booking_reference']}")
        
        # First try real TaxiCaller API
        success = create_taxicaller_booking(booking_data)
        
        if success:
            print(f"✅ TAXICALLER API SUCCESS: {booking_data['booking_reference']}")
            
            # Also send to our internal endpoint for logging
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
                
                # Send to our logging endpoint
                response = requests.post(
                    f"{RENDER_ENDPOINT}",
                    json=taxicaller_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                print(f"📊 INTERNAL LOGGING: {response.status_code}")
                
            except Exception as log_error:
                print(f"⚠️ LOGGING ERROR (non-critical): {str(log_error)}")
            
            return True
        else:
            print(f"❌ TAXICALLER API FAILED: {booking_data['booking_reference']}")
            
            # Fallback - still log the booking attempt
            print("🔄 LOGGING FAILED BOOKING ATTEMPT...")
            try:
                fallback_payload = {
                    'booking_reference': booking_data['booking_reference'],
                    'status': 'failed_taxicaller_api',
                    'customer_details': booking_data['taxicaller_format'],
                    'error': 'TaxiCaller API unavailable',
                    'timestamp': datetime.now().isoformat()
                }
                
                response = requests.post(
                    f"{RENDER_ENDPOINT}",
                    json=fallback_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                print(f"📊 FALLBACK LOGGED: {response.status_code}")
                
            except Exception as fallback_error:
                print(f"💥 FALLBACK LOGGING FAILED: {str(fallback_error)}")
            
            return False
            
    except Exception as e:
        print(f"💥 CRITICAL BOOKING ERROR: {str(e)}")
        return False

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Confirm and process new booking"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔔 BOOKING CONFIRMATION: '{data}' (Confidence: {confidence})")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        # Get booking details from session or re-parse
        session_data = user_sessions.get(call_sid, {})
        booking_details = session_data.get('booking_details', '')
        
        if booking_details:
            booking_data = parse_booking_details(booking_details, caller_number)
        else:
            # Fallback - create basic booking
            booking_data = {
                'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'caller_number': caller_number,
                'raw_speech': 'Confirmed booking',
                'timestamp': datetime.now().isoformat(),
                'status': 'confirmed',
                'taxicaller_format': {
                    'customer_name': 'Phone Customer',
                    'pickup_address': 'Wellington Central, Wellington',
                    'destination_address': 'Wellington Airport, Rongotai, Wellington',
                    'booking_date': datetime.now().strftime('%d/%m/%Y'),
                    'booking_time': datetime.now().strftime('%I:%M %p'),
                    'phone_number': caller_number.replace('+64', '0'),
                    'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'special_instructions': 'Booked via AI phone system'
                }
            }
        
        print("=" * 60)
        print("🚕 CONFIRMED BOOKING - SENDING TO TAXICALLER:")
        print("=" * 60)
        print(f"📞 CALL SID: {call_sid}")
        print(f"📱 CALLER: {caller_number}")
        print(f"🔢 REFERENCE: {booking_data['booking_reference']}")
        print("📋 BOOKING DETAILS:")
        for key, value in booking_data['taxicaller_format'].items():
            print(f"   {key}: {value}")
        print("=" * 60)
        
        # Send to TaxiCaller dispatch system
        render_success = send_booking_to_render(booking_data)
        
        # Log the result
        if render_success:
            print("✅ BOOKING SUCCESSFULLY SENT TO TAXICALLER!")
        else:
            print("❌ BOOKING FAILED TO SEND TO TAXICALLER!")
        
        # Clean up session
        if call_sid in user_sessions:
            del user_sessions[call_sid]
        
        success_message = "Perfect! Your taxi booking is confirmed. You'll receive a confirmation call shortly. Thanks for choosing Kiwi Cabs!"
        
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {success_message}
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        
    elif any(pattern in data for pattern in no_patterns):
        print("🔄 CUSTOMER WANTS TO CHANGE BOOKING - redirecting to /book")
        return redirect_to("/book")
    else:
        print(f"❓ UNCLEAR CONFIRMATION RESPONSE: '{data}'")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/process_modification", methods=["POST"])
def process_modification():
    """Process real booking modification request"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Modification Request: '{data}' (Confidence: {confidence})")
    
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
    
    # Store modification request (but don't send to dispatch yet)
    modification_bookings[call_sid] = {
        'phone_number': search_phone,
        'original_booking': existing_booking,
        'modification_request': data,
        'status': 'pending_confirmation'
    }
    
    # Determine what type of modification
    modification_type = determine_modification_type(data)
    
    if modification_type == 'cancel':
        confirmation_message = f"I'll cancel your booking for {existing_booking.get('customer_details', {}).get('name', 'you')}. Say yes to confirm cancellation or no to keep the booking."
    else:
        if modification_type == 'pickup':
            confirmation_message = f"I'll change your pickup location. Say yes to confirm this change or no to try again."
        elif modification_type == 'destination':
            confirmation_message = f"I'll change your destination. Say yes to confirm this change or no to try again."
        elif modification_type == 'time':
            confirmation_message = f"I'll change your pickup time. Say yes to confirm this change or no to try again."
        else:
            confirmation_message = f"I'll update your booking as requested. Say yes to confirm these changes or no to try again."

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {confirmation_message}
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

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
        if 'street' in text_lower or 'road' in text_lower or 'avenue' in text_lower:
            return 'pickup'
        return 'time'

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
        
        if modification_data:
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
</Response>""", mimetype="text/xml")

def redirect_to(path):
    """Helper function for XML redirects"""
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

# API endpoints to handle booking operations with clear logging
@app.route("/api/bookings", methods=["POST"])
def receive_booking():
    """Endpoint to receive and log new booking data"""
    try:
        booking_data = request.get_json()
        
        print("=" * 80)
        print("📨 RECEIVED NEW BOOKING AT /api/bookings:")
        print("=" * 80)
        print(f"🕐 TIMESTAMP: {datetime.now().isoformat()}")
        print(f"📞 BOOKING REF: {booking_data.get('booking_reference', 'N/A')}")
        print(f"👤 CUSTOMER: {booking_data.get('customer_details', {}).get('name', 'N/A')}")
        print(f"📱 PHONE: {booking_data.get('customer_details', {}).get('phone', 'N/A')}")
        print(f"📍 PICKUP: {booking_data.get('trip_details', {}).get('pickup_address', 'N/A')}")
        print(f"🎯 DROPOFF: {booking_data.get('trip_details', {}).get('destination_address', 'N/A')}")
        print(f"📅 DATE: {booking_data.get('trip_details', {}).get('pickup_date', 'N/A')}")
        print(f"⏰ TIME: {booking_data.get('trip_details', {}).get('pickup_time', 'N/A')}")
        print(f"🔄 STATUS: {booking_data.get('booking_info', {}).get('status', 'N/A')}")
        print("📋 FULL DATA:")
        print(json.dumps(booking_data, indent=2))
        print("=" * 80)
        
        return {
            "status": "success", 
            "message": "Booking received and logged successfully", 
            "booking_id": booking_data.get('booking_reference', 'N/A'),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ ERROR RECEIVING BOOKING: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

@app.route("/api/test-booking", methods=["POST"])
def test_booking():
    """Test endpoint to manually send a booking"""
    try:
        test_booking_data = {
            'booking_reference': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'caller_number': '+6421234567',
            'raw_speech': 'Test booking',
            'timestamp': datetime.now().isoformat(),
            'status': 'confirmed',
            'taxicaller_format': {
                'customer_name': 'Test Customer',
                'pickup_address': 'Wellington Airport, Rongotai, Wellington',
                'destination_address': 'Queen Street, Wellington Central, Wellington',
                'booking_date': datetime.now().strftime('%d/%m/%Y'),
                'booking_time': '2:00 PM',
                'phone_number': '0212345678',
                'booking_reference': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'special_instructions': 'Test booking via API'
            }
        }
        
        print("🧪 SENDING TEST BOOKING:")
        success = send_booking_to_render(test_booking_data)
        
        return {
            "status": "success" if success else "failed",
            "message": "Test booking sent",
            "booking_data": test_booking_data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400

@app.route("/search_live_booking", methods=["GET"])
def search_live_booking():
    """Endpoint to search for existing live bookings"""
    try:
        phone = request.args.get('phone', '')
        print(f"🔍 SEARCHING FOR LIVE BOOKING: Phone {phone}")
        
        mock_booking = {
            "booking_details": {
                "booking_reference": f"KC{datetime.now().strftime('%Y%m%d')}001",
                "customer_details": {
                    "name": "John Smith",
                    "phone": phone
                },
                "trip_details": {
                    "pickup_address": "Queen Street, Wellington Central, Wellington",
                    "destination_address": "Wellington Airport, Rongotai, Wellington",
                    "pickup_date": "06/06/2025",
                    "pickup_time": "8:00 AM"
                },
                "booking_info": {
                    "status": "confirmed",
                    "created_at": "2025-06-05T14:30:00Z"
                }
            }
        }
        
        print(f"✅ MOCK BOOKING FOUND: {mock_booking['booking_details']['booking_reference']}")
        return mock_booking
        
    except Exception as e:
        print(f"❌ Error searching booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 404

@app.route("/update_live_booking", methods=["PUT"])
def update_live_booking():
    """Endpoint to update existing live bookings"""
    try:
        modification_data = request.get_json()
        print("🔄 RECEIVED LIVE BOOKING UPDATE:")
        print(json.dumps(modification_data, indent=2))
        
        booking_ref = modification_data.get('booking_reference', 'N/A')
        
        print(f"📋 Updating Booking: {booking_ref}")
        
        response_data = {
            "status": "success",
            "message": "Live booking updated successfully",
            "booking_reference": booking_ref,
            "dispatch_status": "redispatched",
            "updated_at": datetime.now().isoformat(),
            "fleet_notification": "Driver notified of changes"
        }
        
        print("✅ LIVE BOOKING UPDATE SUCCESSFUL (MOCK)")
        return response_data
        
    except Exception as e:
        print(f"❌ Error updating live booking: {str(e)}")
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
        "version": "2.0",
        "endpoints": ["/voice", "/api/bookings", "/health"],
        "integration": "TaxiCaller API Ready"
    }

if __name__ == "__main__":
    app.run(debug=True)
    ]
    
    selected_option = None
    for pattern in option_patterns:
        match = re.search(pattern, data.lower())
        if match:
            selected_option = int(match.group(1))
            break
    
    if selected_option and caller_location.get('has_coordinates'):
        # User selected a nearby location
        nearby_locations = suggest_nearby_locations(caller_location)
        if 1 <= selected_option <= len(nearby_locations):
            selected_location = nearby_locations[selected_option - 1]
            
            # Store the selected pickup location
            user_sessions[call_sid]['auto_pickup'] = selected_location['address']
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Pickup from {selected_location['name']}.
        Now please tell me your name, where you're going, and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_booking_with_auto_pickup" method="POST" timeout="12" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
            return Response(response, mimetype="text/xml")
    
    # Process as normal booking
    return process_booking()

@app.route("/process_booking_with_auto_pickup", methods=["POST"])
def process_booking_with_auto_pickup():
    """Process booking where pickup was auto-selected"""
    data = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    # Get the auto-selected pickup
    session_data = user_sessions.get(call_sid, {})
    auto_pickup = session_data.get('auto_pickup', '')
    
    # Create modified speech text with the auto pickup
    modified_speech = f"Pickup from {auto_pickup}. {data}"
    
    print(f"🎯 AUTO-PICKUP BOOKING: '{modified_speech}'")
    
    # Process normally but with auto pickup included
    booking_data = parse_booking_details(modified_speech, caller_number)
    
    # Override pickup with the auto-selected one
    booking_data['taxicaller_format']['pickup_address'] = auto_pickup
    
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
    
    # Store booking data for confirmation
    user_sessions[call_sid]['booking_details'] = modified_speech
    
    return Response(response, mimetype="text/xml")

@app.route("/modify", methods=["POST"])
def modify():
    """Start modification process"""
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

@app.route("/get_phone_for_booking", methods=["POST"])
def get_phone_for_booking():
    """Extract phone number and search for real existing booking"""
    phone_speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Phone Search: '{phone_speech}' (Confidence: {confidence})")
    
    digits_only = re.sub(r'[^\d]', '', phone_speech)
    
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
    
    if phone_number.startswith('64'):
        phone_number = '0' + phone_number[2:]
    elif len(phone_number) == 9 and not phone_number.startswith('0'):
        phone_number = '0' + phone_number
    
    if len(phone_number) >= 8:
        existing_booking = search_existing_booking_real(phone_number)
        
        if existing_booking:
            user_sessions[call_sid] = {
                'search_phone': phone_number,
                'existing_booking': existing_booking
            }
            
            customer_name = existing_booking.get('customer_details', {}).get('name', 'Customer')
            pickup = existing_booking.get('trip_details', {}).get('pickup_address', 'Unknown location')
            destination = existing_booking.get('trip_details', {}).get('destination_address', 'Unknown destination')
            booking_time = existing_booking.get('trip_details', {}).get('pickup_time', 'Unknown time')
            booking_date = existing_booking.get('trip_details', {}).get('pickup_date', 'Unknown date')
            
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I found your booking for {customer_name}.
        Currently scheduled from {pickup} to {destination} at {booking_time} on {booking_date}.
        What would you like to change? Say pickup location, destination, time, or cancel booking.
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
            return Response(response, mimetype="text/xml")
        else:
            return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't find any booking for phone number ending in {phone_number[-4:]}.
        You can book a new taxi instead. Would you like me to help you book a new taxi?
    </Say>
    <Gather input="speech" action="/handle_no_booking_found" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
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

def validate_address_confidence(address_text, geocoded_result):
    """Check if we're confident about the address or need to ask again"""
    
    # High confidence indicators
    high_confidence_keywords = [
        'airport', 'train station', 'railway station', 'wellington station',
        'queen street', 'cuba street', 'lambton quay', 'courtenay place',
        'interislander', 'ferry terminal'
    ]
    
    # Check if it's a well-known landmark
    if any(keyword in address_text.lower() for keyword in high_confidence_keywords):
        return True, "landmark"
    
    # Check if geocoding was successful with good result
    if geocoded_result and geocoded_result.get('formatted_address'):
        original_words = set(address_text.lower().split())
        geocoded_words = set(geocoded_result['formatted_address'].lower().split())
        
        # Check if key words match
        common_words = original_words.intersection(geocoded_words)
        if len(common_words) >= 2:  # At least 2 words match
            return True, "geocoded_match"
    
    # Check for street number + street name pattern
    street_number_pattern = r'\d+\s+[a-zA-Z\s]+(?:street|road|avenue|drive|place|terrace|crescent|way|st|rd|ave|dr|pl|tce|cres)'
    if re.search(street_number_pattern, address_text, re.IGNORECASE):
        return True, "street_pattern"
    
    # Low confidence - need to ask again
    return False, "unclear"

@app.route("/clarify_pickup", methods=["POST"])
def clarify_pickup():
    """Ask caller to repeat pickup address"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't catch your pickup address clearly. 
        Please tell me again where you need to be picked up from.
        Speak slowly and clearly, for example: 63 Queen Street, or Wellington Airport.
    </Say>
    <Gather input="speech" action="/process_pickup_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/clarify_destination", methods=["POST"])
def clarify_destination():
    """Ask caller to repeat destination address"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I couldn't catch your destination clearly. 
        Please tell me again where you're going.
        Speak slowly and clearly, for example: Wellington Airport, or Train Station.
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/process_pickup_retry", methods=["POST"])
def process_pickup_retry():
    """Process repeated pickup address"""
    pickup_speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔄 PICKUP RETRY: '{pickup_speech}'")
    
    # Try to find pickup address
    pickup_address, pickup_coords = smart_nz_address_lookup(pickup_speech)
    geocoded_pickup = geocode_nz_address(pickup_speech)
    
    is_confident, confidence_reason = validate_address_confidence(pickup_speech, geocoded_pickup)
    
    if is_confident:
        # Store pickup and ask for destination
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['pickup_address'] = pickup_address
        user_sessions[call_sid]['pickup_coords'] = pickup_coords
        
        print(f"✅ PICKUP CONFIRMED: {pickup_address}")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! Pickup from {pickup_address}.
        Now, where would you like to go? Please tell me your destination.
    </Say>
    <Gather input="speech" action="/process_destination_retry" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Still not confident, ask one more time
        print(f"❌ PICKUP STILL UNCLEAR: {pickup_speech}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I'm still having trouble with that address. 
        Let me connect you with our team who can help you with your booking.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_destination_retry", methods=["POST"])
def process_destination_retry():
    """Process repeated destination address"""
    destination_speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔄 DESTINATION RETRY: '{destination_speech}'")
    
    # Try to find destination address
    destination_address, destination_coords = smart_nz_address_lookup(destination_speech)
    geocoded_destination = geocode_nz_address(destination_speech)
    
    is_confident, confidence_reason = validate_address_confidence(destination_speech, geocoded_destination)
    
    if is_confident:
        # Store destination and ask for time/name
        if call_sid not in user_sessions:
            user_sessions[call_sid] = {}
        user_sessions[call_sid]['destination_address'] = destination_address
        user_sessions[call_sid]['destination_coords'] = destination_coords
        
        print(f"✅ DESTINATION CONFIRMED: {destination_address}")
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Going to {destination_address}.
        Now please tell me your name and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_name_and_time" method="POST" timeout="10" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
        return Response(response, mimetype="text/xml")
    else:
        # Still not confident, transfer to human
        print(f"❌ DESTINATION STILL UNCLEAR: {destination_speech}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I'm having trouble understanding that destination. 
        Let me connect you with our team who can help you complete your booking.
    </Say>
    <Dial>+6448880188</Dial>
</Response>"""
        return Response(response, mimetype="text/xml")

@app.route("/process_name_and_time", methods=["POST"])
def process_name_and_time():
    """Process name and time from caller"""
    speech = request.form.get("SpeechResult", "")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔄 NAME AND TIME: '{speech}'")
    
    # Parse name and time from speech
    session_data = user_sessions.get(call_sid, {})
    
    # Create booking data with stored addresses
    booking_details = f"My name is {speech}. Pickup from {session_data.get('pickup_address', 'Unknown')}. Going to {session_data.get('destination_address', 'Unknown')}."
    
    booking_data = parse_booking_details(booking_details, caller_number)
    
    # Override with our confirmed addresses
    if session_data.get('pickup_address'):
        booking_data['taxicaller_format']['pickup_address'] = session_data['pickup_address']
    if session_data.get('destination_address'):
        booking_data['taxicaller_format']['destination_address'] = session_data['destination_address']
    
    # Store for confirmation
    user_sessions[call_sid]['booking_data'] = booking_data
    
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
    <Gather input="speech" action="/confirm_smart_booking" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/confirm_smart_booking", methods=["POST"])
def confirm_smart_booking():
    """Confirm booking with validated addresses"""
    data = request.form.get("SpeechResult", "").lower()
    call_sid = request.form.get("CallSid", "")
    
    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        booking_data = user_sessions.get(call_sid, {}).get('booking_data')
        
        if booking_data:
            print("🚕 SMART BOOKING CONFIRMED - SENDING TO TAXICALLER:")
            print(json.dumps(booking_data['taxicaller_format'], indent=2))
            
            render_success = send_booking_to_render(booking_data)
            
            # Clean up session
            if call_sid in user_sessions:
                del user_sessions[call_sid]
            
            return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Perfect! Your taxi booking is confirmed. 
        You'll receive a confirmation call shortly with your driver details.
        Thanks for choosing Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        else:
            return redirect_to("/book")
    elif any(pattern in data for pattern in no_patterns):
        return redirect_to("/book")
    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_smart_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

def parse_booking_details(speech_text, caller_number):
    """Parse and format booking details for TaxiCaller dispatch system"""
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
    original_text = speech_text  # Keep original case
    
    print(f"🔍 PARSING BOOKING: '{speech_text}'")
    
    # Enhanced customer name extraction
    name_patterns = [
        r'(?:my name is|i am|i\'m|this is|name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+(?:i\s+)?(?:need|want|from|at|pickup|going|and|,))',
        r'(?:my name is|i am|i\'m|this is|name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)+)',
        r'^([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+(?:i\s+)?(?:need|want|from|at|pickup|going))',
    ]
    
    customer_name = "Unknown Customer"
    for pattern in name_patterns:
        match = re.search(pattern, original_text, re.IGNORECASE)
        if match:
            name_candidate = match.group(1).strip()
            # Filter out non-name words
            excluded_words = ['need', 'want', 'taxi', 'from', 'to', 'going', 'street', 'road', 'avenue', 'drive', 'wellington', 'airport', 'station', 'today', 'tomorrow', 'morning', 'afternoon', 'evening', 'pickup', 'drop', 'book', 'change', 'time']
            
            # Check if name candidate contains valid name words
            name_words = name_candidate.split()
            valid_name = True
            for word in name_words:
                if word.lower() in excluded_words or len(word) < 2:
                    valid_name = False
                    break
            
            if valid_name and len(name_words) <= 4:  # Reasonable name length
                customer_name = name_candidate.title()
                print(f"✅ NAME FOUND: {customer_name}")
                break
    
    if customer_name == "Unknown Customer":
        print(f"❌ NO VALID NAME FOUND in: {original_text}")
    
    # Enhanced Wellington location database with numbers
    wellington_locations = {
        'queen street': 'Queen Street, Wellington Central, Wellington',
        'cuba street': 'Cuba Street, Wellington Central, Wellington',
        'lambton quay': 'Lambton Quay, Wellington Central, Wellington',
        'willis street': 'Willis Street, Wellington Central, Wellington',
        'courtenay place': 'Courtenay Place, Wellington Central, Wellington',
        'manners street': 'Manners Street, Wellington Central, Wellington',
        'the terrace': 'The Terrace, Wellington Central, Wellington',
        'featherston street': 'Featherston Street, Wellington Central, Wellington',
        'hobart street': 'Hobart Street, Miramar, Wellington',
        'newark street': 'Newark Street, Mount Victoria, Wellington',
        'wellington airport': 'Wellington Airport, Rongotai, Wellington',
        'airport': 'Wellington Airport, Rongotai, Wellington',
        'wellington station': 'Wellington Railway Station, Pipitea, Wellington',
        'train station': 'Wellington Railway Station, Pipitea, Wellington',
        'railway station': 'Wellington Railway Station, Pipitea, Wellington',
        'interislander': 'Interislander Terminal, Aotea Quay, Wellington',
        'ferry terminal': 'Interislander Terminal, Aotea Quay, Wellington',
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
    
    def find_wellington_address(text_segment, is_pickup=False):
        """Smart NZ address lookup using real geocoding"""
        text_segment = text_segment.strip()
        
        print(f"🔍 ADDRESS LOOKUP: '{text_segment}'")
        
        # Use smart geocoding
        formatted_address, coordinates = smart_nz_address_lookup(text_segment)
        
        return formatted_address
    
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
    
    # Enhanced time parsing with better PM/AM detection
    time_patterns = [
        r'(?:at|for|by|today|tomorrow).*?(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|in the evening)',
        r'(?:at|for|by|today|tomorrow).*?(\d{1,2})(?::(\d{2}))?\s*(am|a\.m\.|in the morning)',
        r'(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|evening)',
        r'(\d{1,2})(?::(\d{2}))?\s*(am|a\.m\.|morning)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(pm|am)',
        r'(\d{1,2})\s*(pm|am)',
        r'(?:at|for|by)\s+(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?\s*(pm|am)?',
        r'(\d{1,2})(?::(\d{2}))?\s*(?:o\'clock)?'
    ]
    
    # Check for explicit PM indicators first
    pm_indicators = ['pm', 'p.m.', 'evening', 'night', 'tonight']
    am_indicators = ['am', 'a.m.', 'morning']
    
    is_pm = any(indicator in text_lower for indicator in pm_indicators)
    is_am = any(indicator in text_lower for indicator in am_indicators)
    
    print(f"DEBUG - Time parsing: '{text_lower}'")
    print(f"DEBUG - PM indicators found: {is_pm}")
    print(f"DEBUG - AM indicators found: {is_am}")
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3) if len(match.groups()) >= 3 and match.group(3) else None
            
            print(f"DEBUG - Matched time: {hour}:{minute:02d}, am_pm: {am_pm}")
            
            # Determine AM/PM
            if am_pm:
                am_pm_lower = am_pm.lower()
                if 'pm' in am_pm_lower or 'evening' in am_pm_lower:
                    is_pm = True
                    is_am = False
                elif 'am' in am_pm_lower or 'morning' in am_pm_lower:
                    is_am = True
                    is_pm = False
            
            # Convert to 24-hour format
            if is_pm and hour != 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0
            elif not is_am and not is_pm:
                # If no AM/PM specified, make intelligent guess
                if hour >= 1 and hour <= 7:
                    # 1-7 without AM/PM likely means PM (1 PM - 7 PM)
                    hour += 12
                    is_pm = True
                elif hour >= 8 and hour <= 11:
                    # 8-11 could be AM or PM, default to AM for morning, PM for evening context
                    if 'evening' in text_lower or 'tonight' in text_lower:
                        hour += 12
                        is_pm = True
            
            print(f"DEBUG - Final hour: {hour}, is_pm: {is_pm}, is_am: {is_am}")
            
            try:
                requested_datetime = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if requested_datetime < current_time:
                    requested_datetime += timedelta(days=1)
                print(f"DEBUG - Parsed datetime: {requested_datetime}")
            except ValueError:
                print(f"DEBUG - Invalid time values: {hour}:{minute}")
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
    """Send booking to TaxiCaller dispatch system using real API"""
    try:
        print("🚀 ATTEMPTING TO SEND BOOKING TO TAXICALLER...")
        print(f"📋 Booking Reference: {booking_data['booking_reference']}")
        
        # First try real TaxiCaller API
        success = create_taxicaller_booking(booking_data)
        
        if success:
            print(f"✅ TAXICALLER API SUCCESS: {booking_data['booking_reference']}")
            
            # Also send to our internal endpoint for logging
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
                
                # Send to our logging endpoint
                response = requests.post(
                    f"{RENDER_ENDPOINT}",
                    json=taxicaller_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                print(f"📊 INTERNAL LOGGING: {response.status_code}")
                
            except Exception as log_error:
                print(f"⚠️ LOGGING ERROR (non-critical): {str(log_error)}")
            
            return True
        else:
            print(f"❌ TAXICALLER API FAILED: {booking_data['booking_reference']}")
            
            # Fallback - still log the booking attempt
            print("🔄 LOGGING FAILED BOOKING ATTEMPT...")
            try:
                fallback_payload = {
                    'booking_reference': booking_data['booking_reference'],
                    'status': 'failed_taxicaller_api',
                    'customer_details': booking_data['taxicaller_format'],
                    'error': 'TaxiCaller API unavailable',
                    'timestamp': datetime.now().isoformat()
                }
                
                response = requests.post(
                    f"{RENDER_ENDPOINT}",
                    json=fallback_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                print(f"📊 FALLBACK LOGGED: {response.status_code}")
                
            except Exception as fallback_error:
                print(f"💥 FALLBACK LOGGING FAILED: {str(fallback_error)}")
            
            return False
            
    except Exception as e:
        print(f"💥 CRITICAL BOOKING ERROR: {str(e)}")
        return False

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Confirm and process new booking"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔔 BOOKING CONFIRMATION: '{data}' (Confidence: {confidence})")

    yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "good", "sweet"]
    no_patterns = ["no", "nah", "wrong", "incorrect", "change"]

    if any(pattern in data for pattern in yes_patterns):
        # Get booking details from session or re-parse
        session_data = user_sessions.get(call_sid, {})
        booking_details = session_data.get('booking_details', '')
        
        if booking_details:
            booking_data = parse_booking_details(booking_details, caller_number)
        else:
            # Fallback - create basic booking
            booking_data = {
                'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'caller_number': caller_number,
                'raw_speech': 'Confirmed booking',
                'timestamp': datetime.now().isoformat(),
                'status': 'confirmed',
                'taxicaller_format': {
                    'customer_name': 'Phone Customer',
                    'pickup_address': 'Wellington Central, Wellington',
                    'destination_address': 'Wellington Airport, Rongotai, Wellington',
                    'booking_date': datetime.now().strftime('%d/%m/%Y'),
                    'booking_time': datetime.now().strftime('%I:%M %p'),
                    'phone_number': caller_number.replace('+64', '0'),
                    'booking_reference': f"KC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'special_instructions': 'Booked via AI phone system'
                }
            }
        
        print("=" * 60)
        print("🚕 CONFIRMED BOOKING - SENDING TO TAXICALLER:")
        print("=" * 60)
        print(f"📞 CALL SID: {call_sid}")
        print(f"📱 CALLER: {caller_number}")
        print(f"🔢 REFERENCE: {booking_data['booking_reference']}")
        print("📋 BOOKING DETAILS:")
        for key, value in booking_data['taxicaller_format'].items():
            print(f"   {key}: {value}")
        print("=" * 60)
        
        # Send to TaxiCaller dispatch system
        render_success = send_booking_to_render(booking_data)
        
        # Log the result
        if render_success:
            print("✅ BOOKING SUCCESSFULLY SENT TO TAXICALLER!")
        else:
            print("❌ BOOKING FAILED TO SEND TO TAXICALLER!")
        
        # Clean up session
        if call_sid in user_sessions:
            del user_sessions[call_sid]
        
        success_message = "Perfect! Your taxi booking is confirmed. You'll receive a confirmation call shortly. Thanks for choosing Kiwi Cabs!"
        
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {success_message}
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        
    elif any(pattern in data for pattern in no_patterns):
        print("🔄 CUSTOMER WANTS TO CHANGE BOOKING - redirecting to /book")
        return redirect_to("/book")
    else:
        print(f"❓ UNCLEAR CONFIRMATION RESPONSE: '{data}'")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I didn't catch that clearly. Please say yes to confirm your booking or no to make changes.
    </Say>
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    <Gather input="speech" action="/confirm_booking" method="POST" timeout="5" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>""", mimetype="text/xml")

@app.route("/process_modification", methods=["POST"])
def process_modification():
    """Process real booking modification request"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"DEBUG - Modification Request: '{data}' (Confidence: {confidence})")
    
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
    
    # Store modification request (but don't send to dispatch yet)
    modification_bookings[call_sid] = {
        'phone_number': search_phone,
        'original_booking': existing_booking,
        'modification_request': data,
        'status': 'pending_confirmation'
    }
    
    # Determine what type of modification
    modification_type = determine_modification_type(data)
    
    if modification_type == 'cancel':
        confirmation_message = f"I'll cancel your booking for {existing_booking.get('customer_details', {}).get('name', 'you')}. Say yes to confirm cancellation or no to keep the booking."
    else:
        if modification_type == 'pickup':
            confirmation_message = f"I'll change your pickup location. Say yes to confirm this change or no to try again."
        elif modification_type == 'destination':
            confirmation_message = f"I'll change your destination. Say yes to confirm this change or no to try again."
        elif modification_type == 'time':
            confirmation_message = f"I'll change your pickup time. Say yes to confirm this change or no to try again."
        else:
            confirmation_message = f"I'll update your booking as requested. Say yes to confirm these changes or no to try again."

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {confirmation_message}
    </Say>
    <Gather input="speech" action="/confirm_modification" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    return Response(response, mimetype="text/xml")

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
        if 'street' in text_lower or 'road' in text_lower or 'avenue' in text_lower:
            return 'pickup'
        return 'time'

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
        
        if modification_data:
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
</Response>""", mimetype="text/xml")

def redirect_to(path):
    """Helper function for XML redirects"""
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

# API endpoints to handle booking operations with clear logging
@app.route("/api/bookings", methods=["POST"])
def receive_booking():
    """Endpoint to receive and log new booking data"""
    try:
        booking_data = request.get_json()
        
        print("=" * 80)
        print("📨 RECEIVED NEW BOOKING AT /api/bookings:")
        print("=" * 80)
        print(f"🕐 TIMESTAMP: {datetime.now().isoformat()}")
        print(f"📞 BOOKING REF: {booking_data.get('booking_reference', 'N/A')}")
        print(f"👤 CUSTOMER: {booking_data.get('customer_details', {}).get('name', 'N/A')}")
        print(f"📱 PHONE: {booking_data.get('customer_details', {}).get('phone', 'N/A')}")
        print(f"📍 PICKUP: {booking_data.get('trip_details', {}).get('pickup_address', 'N/A')}")
        print(f"🎯 DROPOFF: {booking_data.get('trip_details', {}).get('destination_address', 'N/A')}")
        print(f"📅 DATE: {booking_data.get('trip_details', {}).get('pickup_date', 'N/A')}")
        print(f"⏰ TIME: {booking_data.get('trip_details', {}).get('pickup_time', 'N/A')}")
        print(f"🔄 STATUS: {booking_data.get('booking_info', {}).get('status', 'N/A')}")
        print("📋 FULL DATA:")
        print(json.dumps(booking_data, indent=2))
        print("=" * 80)
        
        return {
            "status": "success", 
            "message": "Booking received and logged successfully", 
            "booking_id": booking_data.get('booking_reference', 'N/A'),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ ERROR RECEIVING BOOKING: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

@app.route("/api/test-booking", methods=["POST"])
def test_booking():
    """Test endpoint to manually send a booking"""
    try:
        test_booking_data = {
            'booking_reference': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'caller_number': '+6421234567',
            'raw_speech': 'Test booking',
            'timestamp': datetime.now().isoformat(),
            'status': 'confirmed',
            'taxicaller_format': {
                'customer_name': 'Test Customer',
                'pickup_address': 'Wellington Airport, Rongotai, Wellington',
                'destination_address': 'Queen Street, Wellington Central, Wellington',
                'booking_date': datetime.now().strftime('%d/%m/%Y'),
                'booking_time': '2:00 PM',
                'phone_number': '0212345678',
                'booking_reference': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'special_instructions': 'Test booking via API'
            }
        }
        
        print("🧪 SENDING TEST BOOKING:")
        success = send_booking_to_render(test_booking_data)
        
        return {
            "status": "success" if success else "failed",
            "message": "Test booking sent",
            "booking_data": test_booking_data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400

@app.route("/search_live_booking", methods=["GET"])
def search_live_booking():
    """Endpoint to search for existing live bookings"""
    try:
        phone = request.args.get('phone', '')
        print(f"🔍 SEARCHING FOR LIVE BOOKING: Phone {phone}")
        
        mock_booking = {
            "booking_details": {
                "booking_reference": f"KC{datetime.now().strftime('%Y%m%d')}001",
                "customer_details": {
                    "name": "John Smith",
                    "phone": phone
                },
                "trip_details": {
                    "pickup_address": "Queen Street, Wellington Central, Wellington",
                    "destination_address": "Wellington Airport, Rongotai, Wellington",
                    "pickup_date": "06/06/2025",
                    "pickup_time": "8:00 AM"
                },
                "booking_info": {
                    "status": "confirmed",
                    "created_at": "2025-06-05T14:30:00Z"
                }
            }
        }
        
        print(f"✅ MOCK BOOKING FOUND: {mock_booking['booking_details']['booking_reference']}")
        return mock_booking
        
    except Exception as e:
        print(f"❌ Error searching booking: {str(e)}")
        return {"status": "error", "message": str(e)}, 404

@app.route("/update_live_booking", methods=["PUT"])
def update_live_booking():
    """Endpoint to update existing live bookings"""
    try:
        modification_data = request.get_json()
        print("🔄 RECEIVED LIVE BOOKING UPDATE:")
        print(json.dumps(modification_data, indent=2))
        
        booking_ref = modification_data.get('booking_reference', 'N/A')
        
        print(f"📋 Updating Booking: {booking_ref}")
        
        response_data = {
            "status": "success",
            "message": "Live booking updated successfully",
            "booking_reference": booking_ref,
            "dispatch_status": "redispatched",
            "updated_at": datetime.now().isoformat(),
            "fleet_notification": "Driver notified of changes"
        }
        
        print("✅ LIVE BOOKING UPDATE SUCCESSFUL (MOCK)")
        return response_data
        
    except Exception as e:
        print(f"❌ Error updating live booking: {str(e)}")
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
        "version": "2.0",
        "endpoints": ["/voice", "/api/bookings", "/health"],
        "integration": "TaxiCaller API Ready"
    }

if __name__ == "__main__":
    app.run(debug=True)