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
        return redirect_to("/book_with_location")
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
        Please tell me your name, pickup address, destination, and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="3" finishOnKey=""/>
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

@app.route("/book", methods=["POST"])
def book():
    """Standard booking process"""
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Great! I'll help you book your taxi.
        Please tell me your name, pickup address, destination, and what time you need the taxi.
    </Say>
    <Gather input="speech" action="/process_booking" method="POST" timeout="15" language="en-NZ" speechTimeout="3" finishOnKey=""/>
</Response>"""
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

def redirect_to(path):
    """Helper function for XML redirects"""
    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{path}</Redirect>
</Response>""", mimetype="text/xml")

@app.route("/process_booking", methods=["POST"])
def process_booking():
    """Process new booking details with Wellington service area validation"""
    data = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    call_sid = request.form.get("CallSid", "")
    caller_number = request.form.get("From", "")
    
    print(f"🎯 PROCESSING BOOKING: '{data}' (Confidence: {confidence})")
    
    # Simple confirmation for now
    current_time = datetime.now()
    booking_ref = f"KC{current_time.strftime('%Y%m%d%H%M%S')}"
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Thank you for your booking details. 
        Your booking reference is {booking_ref}.
        We'll process your taxi request and call you back shortly with driver details.
        Thanks for choosing Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>"""
    
    print(f"✅ BOOKING PROCESSED: Reference {booking_ref}")
    print(f"📋 Customer said: '{data}'")
    
    return Response(response, mimetype="text/xml")

@app.route("/get_phone_for_booking", methods=["POST"])
def get_phone_for_booking():
    """Handle phone number for booking modification"""
    phone_speech = request.form.get("SpeechResult", "")
    
    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aria-Neural" language="en-NZ">
        Thanks! I'm checking for your booking. 
        Our team will call you back shortly to help with your booking changes.
        Thanks for calling Kiwi Cabs!
    </Say>
    <Hangup/>
</Response>"""
    
    print(f"📞 MODIFICATION REQUEST: Phone search '{phone_speech}'")
    
    return Response(response, mimetype="text/xml")

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Kiwi Cabs AI IVR", "version": "3.0"}

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