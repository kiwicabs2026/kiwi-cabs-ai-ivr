import os
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
# Simple booking storage - stores all bookings by phone number
booking_storage = {}

def parse_booking_speech(speech_text):
    """Parse booking details from speech input including NZ date format"""
    booking_data = {
        'name': '',
        'pickup_address': '',
        'destination': '',
        'pickup_time': '',
        'pickup_date': '',
        'raw_speech': speech_text
    }
    
    # Extract name - improved patterns
    name_patterns = [
        r"(?:my name is|I'm|this is)\s+([A-Za-z\s]+?)(?:\s|$)",
        r"and my name is\s+([A-Za-z\s]+?)(?:\s|$)",
        r"(?:^|\s)([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s|$)",  # Match "Sam Abraham" pattern
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            potential_name = match.group(1).strip()
            # Filter out common non-name words
            if not any(word in potential_name.lower() for word in ['need', 'want', 'going', 'from', 'taxi', 'booking']):
                booking_data['name'] = potential_name
                break
    
    # Extract pickup address - simpler and cleaner
    pickup_patterns = [
        r"(?:from|pick up from|pickup from)\s+([^,]+?)(?:\s+(?:to|going|I|and))",
        r"(?:from|pick up from|pickup from)\s+([^,]+)$"
    ]
    
    for pattern in pickup_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            pickup = match.group(1).strip()
            # Simple cleanup
            pickup = pickup.replace("number ", "").replace(" I'm", "")
            booking_data['pickup_address'] = pickup
            break
    
    # Extract destination - MUCH simpler and cleaner
    destination_patterns = [
        r"(?:to|going to)\s+([^.]+?)(?:\s+(?:tomorrow|today|tonight|at|\d|on|date))",
        r"(?:to|going to)\s+([^.]+)$"
    ]
    
    for pattern in destination_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            destination = match.group(1).strip()
            # Simple cleanup - just fix obvious problems
            destination = destination.replace("wellington wellington", "wellington")
            if "hospital" in destination.lower():
                destination = "Wellington Hospital"
            elif "airport" in destination.lower():
                destination = "Wellington Airport"
            elif "station" in destination.lower():
                destination = "Wellington Railway Station"
            
            booking_data['destination'] = destination
            break
    
    # Extract date - intelligent parsing for natural language
    from datetime import datetime, timedelta
    
    # AFTER TOMORROW keywords = day after tomorrow (+2 days)
    after_tomorrow_keywords = ["after tomorrow", "day after tomorrow", "the day after tomorrow"]
    
    # TOMORROW keywords = next day (+1 day)
    tomorrow_keywords = ["tomorrow morning", "tomorrow afternoon", "tomorrow evening", "tomorrow night", "tomorrow"]
    
    # TODAY keywords = current date (same day)
    today_keywords = ["tonight", "today", "later today", "this afternoon", 
                      "this evening", "this morning"]
    
    # Smart parsing - check longer phrases first
    if any(keyword in speech_text.lower() for keyword in after_tomorrow_keywords):
        day_after_tomorrow = datetime.now() + timedelta(days=2)
        booking_data['pickup_date'] = day_after_tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in tomorrow_keywords):
        tomorrow = datetime.now() + timedelta(days=1)
        booking_data['pickup_date'] = tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in today_keywords):
        today = datetime.now()
        booking_data['pickup_date'] = today.strftime("%d/%m/%Y")
    else:
        # Try to find explicit date formats
        date_patterns = [
            r"(?:date|on)\s+(\d{1,2}/\d{1,2}/\d{4})",
            r"(?:date|on)\s+(\d{1,2}/\d{1,2}/\d{2})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{2})"
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, speech_text, re.IGNORECASE)
            if match:
                booking_data['pickup_date'] = match.group(1).strip()
                break
    
    # Extract time - improved patterns
    time_patterns = [
        r"time\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(quarter\s+past\s+\d{1,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(half\s+past\s+\d{1,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"(?:today|tomorrow)\s+at\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))"
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            time_str = match.group(1).strip()
            # Convert quarter past, half past
            if "quarter past" in time_str:
                time_str = time_str.replace("quarter past ", "").replace("quarter past", "")
                hour = time_str.split()[0]
                ampm = time_str.split()[-1] if len(time_str.split()) > 1 else ""
                time_str = f"{hour}:15 {ampm}"
            elif "half past" in time_str:
                time_str = time_str.replace("half past ", "").replace("half past", "")
                hour = time_str.split()[0]
                ampm = time_str.split()[-1] if len(time_str.split()) > 1 else ""
                time_str = f"{hour}:30 {ampm}"
            
            booking_data['pickup_time'] = time_str
            break
    
    return booking_data

def send_booking_to_api(booking_data, caller_number):
    """Send booking to TaxiCaller API or Render endpoint"""
    try:
        api_data = {
            "customer_name": booking_data['name'],
            "phone": caller_number,
            "pickup_address": booking_data['pickup_address'],
            "destination": booking_data['destination'],
            "pickup_time": booking_data['pickup_time'],
            "pickup_date": booking_data['pickup_date'],
            "booking_reference": caller_number.replace('+', '').replace('-', '').replace(' ', ''),
            "service": "taxi",
            "created_via": "ai_ivr",
            "raw_speech": booking_data['raw_speech']
        }
        
        # Try TaxiCaller API first
        if TAXICALLER_API_KEY:
            headers = {
                "Authorization": f"Bearer {TAXICALLER_API_KEY}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{TAXICALLER_BASE_URL}/bookings",
                json=api_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ BOOKING SENT TO TAXICALLER: {response.status_code}")
                return True, response.json()
        
        # Fallback to Render endpoint
        response = requests.post(
            RENDER_ENDPOINT,
            json=api_data,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ BOOKING SENT TO RENDER: {response.status_code}")
            return True, response.json()
        else:
            print(f"❌ API ERROR: {response.status_code} - {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ API SEND ERROR: {str(e)}")
        return False, None

def detect_landline_location(caller_number):
    """Detect location from New Zealand landline area codes"""
    try:
        clean_number = caller_number.replace('+64', '').replace(' ', '').replace('-', '')
        
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

def get_caller_location(request_data):
    """Enhanced caller location detection with landline support"""
    try:
        caller_number = request_data.get('From', '')
        
        landline_info = detect_landline_location(caller_number)
        
        if landline_info and landline_info.get('is_landline'):
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
        
        elif landline_info and landline_info.get('is_mobile'):
            print(f"📱 MOBILE NUMBER - trying GPS detection...")
        
        caller_country = request_data.get('CallerCountry', '')
        caller_state = request_data.get('CallerState', '')
        caller_city = request_data.get('CallerCity', '')
        caller_zip = request_data.get('CallerZip', '')
        
        caller_lat = request_data.get('CallerLat', '')
        caller_lon = request_data.get('CallerLon', '')
        
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
            'city': 'Wellington',
            'state': '',
            'country': 'New Zealand',
            'zip_code': '',
            'is_landline': False,
            'confidence': 'default',
            'formatted_address': 'Wellington, New Zealand'
        }

def validate_wellington_service_area(caller_location, booking_addresses=None):
    """Validate that service request is within Wellington region"""
    
    wellington_service_area = {
        'area_codes': ['04'],
        'region_name': 'Wellington Region',
        'service_cities': [
            'wellington', 'lower hutt', 'upper hutt', 'porirua', 'kapiti coast',
            'paraparaumu', 'waikanae', 'eastbourne', 'petone', 'johnsonville'
        ],
        'coordinates_bounds': {
            'north': -40.8,
            'south': -41.5,
            'west': 174.6,
            'east': 175.2
        }
    }
    
    print(f"🌍 VALIDATING SERVICE AREA...")
    
    if caller_location and caller_location.get('is_landline'):
        area_code = caller_location.get('area_code', '')
        
        if area_code not in wellington_service_area['area_codes']:
            print(f"❌ OUTSIDE SERVICE AREA: Area code {area_code} not in Wellington region")
            return {
                'in_service_area': False,
                'reason': 'outside_wellington_region',
                'caller_region': caller_location.get('region', 'Unknown'),
                'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. I can see you're calling from {caller_location.get('region', 'outside Wellington')}."
            }
    
    if caller_location and caller_location.get('has_coordinates'):
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
    
    if caller_location:
        city = caller_location.get('city', '').lower()
        if city and city not in wellington_service_area['service_cities']:
            wellington_variations = ['wellington', 'wgtn', 'welly']
            if not any(var in city for var in wellington_variations):
                print(f"❌ OUTSIDE SERVICE AREA: City '{city}' not in Wellington region")
                return {
                    'in_service_area': False,
                    'reason': 'outside_wellington_city',
                    'caller_city': city,
                    'message': f"Sorry, Kiwi Cabs operates only in the Wellington region. I can see you're calling from {city.title()}."
                }
    
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
    """Enhanced Wellington address validation"""
    if not address:
        return True
    
    address_lower = address.lower()
    
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
    
    for keyword in wellington_keywords:
        if keyword in address_lower:
            print(f"✅ WELLINGTON ADDRESS CONFIRMED: '{keyword}' found in '{address}'")
            return True
    
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
    
    outside_airports = ['auckland airport', 'akl airport', 'christchurch airport', 'chc airport']
    for airport in outside_airports:
        if airport in address_lower:
            print(f"❌ NON-WELLINGTON AIRPORT: '{airport}' found in '{address}'")
            return False
    
    wellington_landmarks = [
        'airport', 'train station', 'railway station', 'wellington station',
        'interislander', 'ferry terminal', 'parliament', 'beehive',
        'te papa', 'cuba mall', 'botanic garden', 'cable car'
    ]
    
    for landmark in wellington_landmarks:
        if landmark in address_lower:
            print(f"✅ WELLINGTON LANDMARK DETECTED: '{landmark}' in '{address}'")
            return True
    
    print(f"⚠️ UNCLEAR ADDRESS: '{address}' - assuming Wellington region")
    return True

@app.route("/voice", methods=["POST"])
def voice():
    """Initial greeting and menu options"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/menu" input="speech" method="POST" timeout="6" language="en-NZ" speechTimeout="2" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Kia ora, and welcome to Kiwi Cabs.
            Please listen carefully as we have upgraded our booking system.
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
    """Smart menu processing - understands natural language intent"""
    data = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    print(f"🧠 SMART INTENT DETECTION: '{data}' (Confidence: {confidence})")

    # MODIFICATION/CHANGE INTENT - lots of ways people say this
    modify_keywords = [
        # Direct change requests - MOST COMMON
        "change", "modify", "alter", "update", "adjust", "switch", "move", "shift", "edit",
        "change booking", "modify booking", "change my booking", "modify my booking",
        # Existing booking references  
        "i have a booking", "my booking", "existing booking", "current booking", "booked already",
        "already booked", "previous booking", "earlier booking", "made a booking", "have booking",
        # Time/detail changes
        "change the time", "different time", "new time", "wrong time", "make it", "change it",
        "instead of", "not at", "change from", "change to", "move from", "move to",
        # Cancel requests
        "cancel", "delete", "remove", "don't want", "not needed", "won't need", "cancel booking"
    ]

    # NEW BOOKING INTENT - ways people ask for new rides
    booking_keywords = [
        # Direct booking requests
        "book", "need", "want", "get", "order", "arrange", "schedule", "reserve",
        "i need a taxi", "need a ride", "want a cab", "get me a taxi", "book a taxi",
        "need transport", "require transport", "pickup", "collect me", "take me",
        # Time-based requests
        "taxi for", "ride for", "cab for", "transport for", "going to", "travel to",
        "tomorrow", "today", "tonight", "after tomorrow", "later", "morning", "evening",
        # Location-based requests  
        "from", "to the", "airport", "hospital", "station", "pick me up", "drop me"
    ]

    # HUMAN TRANSFER INTENT - want to talk to real person
    human_keywords = [
        # Direct requests
        "human", "person", "operator", "staff", "team", "agent", "representative",
        "speak with", "talk to", "connect me", "transfer me", "put me through",
        # Complaints/problems
        "complaint", "problem", "issue", "help", "assistance", "can't understand",
        "not working", "difficult", "confused", "frustrated", "manager", "supervisor"
    ]

    # SMART INTENT DETECTION - check modification FIRST (most specific)
    print(f"🔍 CHECKING FOR MODIFICATION KEYWORDS...")
    modification_detected = any(keyword in data for keyword in modify_keywords)
    print(f"🔍 MODIFICATION DETECTED: {modification_detected}")
    
    if modification_detected:
        print(f"🔧 ROUTING TO: MODIFICATION FLOW")
        return redirect_to("/modify_booking")
    
    print(f"🔍 CHECKING FOR HUMAN TRANSFER...")
    if any(keyword in data for keyword in human_keywords):
        print(f"👤 ROUTING TO: HUMAN TRANSFER") 
        return redirect_to("/team")
    
    print(f"🔍 CHECKING FOR NEW BOOKING...")
    if any(keyword in data for keyword in booking_keywords):
        print(f"📞 ROUTING TO: NEW BOOKING")
        return redirect_to("/book_with_location")
    
    print(f"❓ NO CLEAR INTENT - asking for clarification")
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

@app.route("/book_with_location", methods=["POST"])
def book_with_location():
    """Start booking process with location detection and service area validation"""
    request_data = dict(request.form)
    
    caller_location = get_caller_location(request_data)
    call_sid = request.form.get("CallSid", "")
    
    validation_result = validate_wellington_service_area(caller_location)
    
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {}
    user_sessions[call_sid]['caller_location'] = caller_location
    user_sessions[call_sid]['validation_result'] = validation_result
    
    if not validation_result['in_service_area']:
        print(f"🚫 CALL OUTSIDE SERVICE AREA: {validation_result['reason']}")
        return redirect_to("/outside_service_area")
    
    print(f"✅ CALL WITHIN WELLINGTON SERVICE AREA - proceeding with booking")
    
    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I'll help you book your taxi.
        Please speak clearly and tell me your name, pickup address, destination, date, and time.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="20" language="en-NZ" speechTimeout="4" finishOnKey="" enhanced="true"/>
</Response>"""
    return Response(response_xml, mimetype="text/xml")

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

@app.route("/process_booking", methods=["POST"])
def process_booking():
    """Process new booking details with enhanced parsing - confirmation step"""
    speech_data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🎯 PROCESSING BOOKING: '{speech_data}' (Confidence: {confidence})")
    
    # Process speech regardless of confidence - Twilio speech recognition issues
    if not speech_data or speech_data.strip() == "":
        print(f"⚠️ EMPTY SPEECH - asking caller to repeat")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I didn't hear anything. Please speak your booking details clearly.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="25" language="en-NZ" speechTimeout="5" finishOnKey=""/>
</Response>""", mimetype="text/xml")
    
    print(f"✅ PROCESSING SPEECH: '{speech_data}'")
    
    # Parse the speech into structured booking data
    booking_data = parse_booking_speech(speech_data)
    
    print(f"📋 PARSED BOOKING DATA:")
    print(f"   👤 Name: {booking_data['name']}")
    print(f"   📍 Pickup: {booking_data['pickup_address']}")
    print(f"   🎯 Destination: {booking_data['destination']}")
    print(f"   🕐 Time: {booking_data['pickup_time']}")
    print(f"   📅 Date: {booking_data['pickup_date']}")
    
    # Check if pickup is from airport - reject these bookings
    pickup_address = booking_data.get('pickup_address', '').lower()
    airport_pickup_keywords = ['airport', 'wellington airport', 'wlg airport', 'terminal']
    
    if any(keyword in pickup_address for keyword in airport_pickup_keywords):
        print(f"✈️ AIRPORT PICKUP DETECTED - rejecting booking from: {pickup_address}")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        You don't need to book a taxi from the airport as we have taxis waiting at the airport rank.
        Thank you for calling Kiwi Cabs and goodbye!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")

    # Validate Wellington addresses
    session_data = user_sessions.get(call_sid, {})
    booking_addresses = {
        'pickup': booking_data['pickup_address'],
        'destination': booking_data['destination']
    }
    
    validation_result = validate_wellington_service_area(
        session_data.get('caller_location'), 
        booking_addresses
    )
    
    if not validation_result['in_service_area']:
        return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {validation_result['message']}
        Thanks for calling!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
    
    # Store booking data in session for confirmation
    if call_sid not in user_sessions:
        user_sessions[call_sid] = {}
    user_sessions[call_sid]['pending_booking'] = booking_data
    user_sessions[call_sid]['caller_number'] = caller_number
    
    # Create clean confirmation message
    confirmation_parts = []
    
    if booking_data['name']:
        confirmation_parts.append(booking_data['name'])
    
    if booking_data['pickup_address']:
        confirmation_parts.append(f"from {booking_data['pickup_address']}")
    
    if booking_data['destination']:
        confirmation_parts.append(f"to {booking_data['destination']}")
    
    if booking_data['pickup_date']:
        confirmation_parts.append(booking_data['pickup_date'])
    
    if booking_data['pickup_time']:
        confirmation_parts.append(booking_data['pickup_time'])
    
    # Join all parts with commas
    confirmation_text = ", ".join(confirmation_parts) if confirmation_parts else "incomplete booking details"
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/confirm_booking" input="speech" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            {confirmation_text}.
            Is this correct? Say yes to confirm or no to make changes.
        </Say>
    </Gather>
    <Redirect>/process_booking</Redirect>
</Response>"""
    
    print(f"❓ AWAITING CONFIRMATION for booking: {booking_data['name']} - {booking_data['pickup_address']} to {booking_data['destination']}")
    
    return Response(response, mimetype="text/xml")

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    """Handle booking confirmation from caller"""
    confirmation_speech = request.form.get("SpeechResult", "").lower()
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    
    print(f"🔍 CONFIRMATION RESPONSE: '{confirmation_speech}' (Confidence: {confidence})")
    
    # Get stored booking data
    session_data = user_sessions.get(call_sid, {})
    booking_data = session_data.get('pending_booking', {})
    caller_number = session_data.get('caller_number', '')
    
    if not booking_data:
        print(f"❌ NO BOOKING DATA FOUND for call_sid: {call_sid}")
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Sorry, I seem to have lost your booking details. Let's start over.
    </Say>
    <Redirect>/book_with_location</Redirect>
</Response>""", mimetype="text/xml")
    
    # Check for confirmation keywords
    confirm_keywords = ["yes", "yeah", "yep", "true", "correct", "right", "agree", "confirm"]
    deny_keywords = ["no", "nope", "wrong", "incorrect", "change", "edit", "modify"]
    
    is_confirmed = any(keyword in confirmation_speech for keyword in confirm_keywords)
    is_denied = any(keyword in confirmation_speech for keyword in deny_keywords)
    
    print(f"🔍 CONFIRMATION CHECK: confirmed={is_confirmed}, denied={is_denied}")
    
    if is_confirmed:
        print(f"✅ BOOKING CONFIRMED by caller")
        
        # Immediate hangup - no other processing
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Thank you for choosing Kiwi Cabs! Your phone number is your booking reference. Goodbye!
    </Say>
    <Hangup/>
</Response>""", mimetype="text/xml")
        
    elif is_denied:
        print(f"❌ BOOKING DENIED by caller - asking for new details")
        
        # Clean up session data
        try:
            if call_sid in user_sessions:
                user_sessions[call_sid].pop('pending_booking', None)
        except Exception as e:
            print(f"⚠️ ERROR CLEANING SESSION: {str(e)}")
        
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        No problem! Let's try again.
        Please tell me your name, pickup address, destination, date, and time.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="20" language="en-NZ" speechTimeout="4" finishOnKey="" enhanced="true"/>
</Response>"""
        
        return Response(response, mimetype="text/xml")
        
    else:
        print(f"❓ UNCLEAR CONFIRMATION - asking again")
        
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/confirm_booking" input="speech" method="POST" timeout="8" language="en-NZ" speechTimeout="2" finishOnKey="">
        <Say voice="Polly.Aria-Neural" language="en-NZ">
            Sorry, I didn't catch that clearly.
            Is the booking correct? Say yes to confirm or no to make changes.
        </Say>
    </Gather>
    <Redirect>/process_booking</Redirect>
</Response>"""
        
        return Response(response, mimetype="text/xml")

def format_phone_for_speech(phone_number):
    """Format phone number for natural speech"""
    # Remove + and spaces
    clean = phone_number.replace('+', '').replace('-', '').replace(' ', '')
    
    # Format as groups of digits
    if len(clean) >= 10:
        # For NZ numbers like 64220881234
        if clean.startswith('64'):
            formatted = f"zero six four, {clean[2:3]} {clean[3:4]} {clean[4:5]}, {clean[5:6]} {clean[6:7]} {clean[7:8]}, {clean[8:9]} {clean[9:10]} {clean[10:11]} {clean[11:12] if len(clean) > 11 else ''}"
        else:
            # Group digits naturally
            formatted = ' '.join(clean[i:i+3] for i in range(0, len(clean), 3))
    else:
        # For shorter numbers
        formatted = ' '.join(clean)
    
    return formatted.strip()

@app.route("/modify_booking", methods=["POST"])
def modify_booking():
    """Smart modification process - finds existing booking and shows details"""
    caller_number = request.form.get("From", "")
    clean_phone = caller_number.replace('+', '').replace('-', '').replace(' ', '')
    
    print(f"🔍 LOOKING FOR BOOKING: {clean_phone}")
    print(f"📋 STORAGE CONTENTS: {list(booking_storage.keys())}")
    
    # Look up existing booking
    if clean_phone in booking_storage:
        booking = booking_storage[clean_phone]
        print(f"✅ FOUND EXISTING BOOKING: {booking}")
        
        # Format phone for speech
        readable_phone = format_phone_for_speech(caller_number)
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I found your booking: {booking['customer_name']}, {booking['pickup_date']}, {booking['pickup_time']}, from {booking['pickup_address']}, to {booking['destination']}.
        What would you like to change?
    </Say>
    <Gather input="speech" action="/process_modification" method="POST" timeout="15" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
    else:
        print(f"❌ NO BOOKING FOUND for {clean_phone}")
        print(f"📋 Available bookings: {list(booking_storage.keys())}")
        
        # Format phone for speech  
        readable_phone = format_phone_for_speech(caller_number)
        
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        I couldn't find a booking for your number {readable_phone}. 
        You can make a new booking or speak with our team.
        What would you like to do?
    </Say>
    <Gather input="speech" action="/menu" method="POST" timeout="10" language="en-NZ" speechTimeout="2" finishOnKey=""/>
</Response>"""
    
    return Response(response, mimetype="text/xml")

@app.route("/process_modification", methods=["POST"])
def process_modification():
    """Process the booking modification"""
    modification_data = request.form.get("SpeechResult", "")
    caller_number = request.form.get("From", "")
    
    print(f"🔧 PROCESSING MODIFICATION: '{modification_data}' for booking {caller_number}")
    
    # Try to update booking via API
    try:
        modification_request = {
            "phone": caller_number,
            "modification": modification_data,
            "action": "modify_booking"
        }
        
        # Send modification to our API endpoint
        response = requests.post(
            f"{RENDER_ENDPOINT.replace('/api/bookings', '/api/modify')}",
            json=modification_request,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ MODIFICATION SENT TO API")
            message = f"Your booking has been updated. Your booking reference is {caller_number}. Thanks for calling Kiwi Cabs!"
        else:
            print(f"❌ MODIFICATION API FAILED")
            message = f"I've noted your request to modify your booking. Our team will call you back shortly at {caller_number}. Thanks for calling Kiwi Cabs!"
    except:
        print(f"❌ MODIFICATION API ERROR")
        message = f"I've noted your request to modify your booking. Our team will call you back shortly at {caller_number}. Thanks for calling Kiwi Cabs!"
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        {message}
    </Say>
    <Hangup/>
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
    <Dial>+6448966156</Dial>
</Response>"""
    return Response(response, mimetype="text/xml")

def redirect_to(path):
    """Helper function for XML redirects"""
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Kiwi Cabs AI IVR", "version": "3.0"}

@app.route("/api/modify", methods=["POST"])
def api_modify():
    """Handle booking modifications"""
    try:
        modification_data = request.get_json()
        phone = modification_data.get('phone')
        modification = modification_data.get('modification')
        
        print(f"🔧 MODIFICATION REQUEST:")
        print(f"   📞 Phone: {phone}")
        print(f"   📝 Change: {modification}")
        
        # Try to send modification to TaxiCaller
        if TAXICALLER_API_KEY:
            try:
                modification_payload = {
                    "customer_phone": phone,
                    "modification_request": modification,
                    "action": "update_booking"
                }
                
                headers = {
                    "Authorization": f"Bearer {TAXICALLER_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                response = requests.put(
                    f"{TAXICALLER_BASE_URL}/bookings/modify",
                    json=modification_payload,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    print(f"✅ MODIFICATION SENT TO TAXICALLER")
                    return {"status": "success", "message": "Booking modified"}, 200
                    
            except Exception as e:
                print(f"❌ TAXICALLER MODIFICATION ERROR: {str(e)}")
        
        # Fallback: Log modification request
        print(f"📝 MODIFICATION LOGGED")
        return {"status": "logged", "message": "Modification request logged"}, 200
        
    except Exception as e:
        print(f"❌ MODIFICATION ENDPOINT ERROR: {str(e)}")
        return {"status": "error", "message": "Failed to process modification"}, 500
    """Receive AI booking data and process it"""
    try:
        # Get booking data from AI
        booking_data = request.get_json()
        
        print(f"📥 RECEIVED BOOKING DATA:")
        print(f"   👤 Customer: {booking_data.get('customer_name', 'Unknown')}")
        print(f"   📞 Phone: {booking_data.get('phone', 'Unknown')}")
        print(f"   📍 Pickup: {booking_data.get('pickup_address', 'Unknown')}")
        print(f"   🎯 Destination: {booking_data.get('destination', 'Unknown')}")
        print(f"   📅 Date: {booking_data.get('pickup_date', 'Unknown')}")
        print(f"   🕐 Time: {booking_data.get('pickup_time', 'Unknown')}")
        print(f"   🔗 Reference: {booking_data.get('booking_reference', 'Unknown')}")
        
        # Store booking data on Render for lookup later
        clean_phone = booking_data.get('phone', '').replace('+', '').replace('-', '').replace(' ', '')
        booking_storage[clean_phone] = {
            'customer_name': booking_data.get('customer_name', ''),
            'phone': booking_data.get('phone', ''),
            'pickup_address': booking_data.get('pickup_address', ''),
            'destination': booking_data.get('destination', ''),
            'pickup_date': booking_data.get('pickup_date', ''),
            'pickup_time': booking_data.get('pickup_time', ''),
            'booking_reference': booking_data.get('booking_reference', ''),
            'created_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        print(f"💾 BOOKING SAVED TO RENDER STORAGE: {clean_phone}")
        
        # Here you can:
        # 1. Save to database
        # 2. Send to TaxiCaller API
        # 3. Process the booking
        
        # For now, let's try to send to TaxiCaller if API key exists
        if TAXICALLER_API_KEY:
            try:
                # Format data for TaxiCaller API
                taxicaller_data = {
                    "customer": {
                        "name": booking_data.get('customer_name', ''),
                        "phone": booking_data.get('phone', '')
                    },
                    "pickup": {
                        "address": booking_data.get('pickup_address', ''),
                        "date": booking_data.get('pickup_date', ''),
                        "time": booking_data.get('pickup_time', '')
                    },
                    "destination": {
                        "address": booking_data.get('destination', '')
                    },
                    "reference": booking_data.get('booking_reference', ''),
                    "source": "ai_ivr"
                }
                
                headers = {
                    "Authorization": f"Bearer {TAXICALLER_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                # Send to TaxiCaller
                response = requests.post(
                    f"{TAXICALLER_BASE_URL}/bookings",
                    json=taxicaller_data,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    print(f"✅ BOOKING SENT TO TAXICALLER SUCCESSFULLY")
                    return {
                        "status": "success",
                        "message": "Booking created in TaxiCaller",
                        "taxicaller_response": response.json()
                    }, 200
                else:
                    print(f"❌ TAXICALLER ERROR: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ TAXICALLER API ERROR: {str(e)}")
        
        # Fallback: Just log the booking
        print(f"📝 BOOKING LOGGED SUCCESSFULLY")
        return {
            "status": "success", 
            "message": "Booking received and logged",
            "booking_id": booking_data.get('booking_reference', 'unknown')
        }, 200
        
    except Exception as e:
        print(f"❌ BOOKING ENDPOINT ERROR: {str(e)}")
        return {
            "status": "error",
            "message": "Failed to process booking"
        }, 500

@app.route("/", methods=["GET"])
def home():
    """Root endpoint with service info"""
    return {
        "message": "Kiwi Cabs AI IVR System", 
        "version": "3.0",
        "endpoints": ["/voice", "/health"],
        "service_area": "Wellington Region Only"
    }

if __name__ == "__main__":
    app.run(debug=True)