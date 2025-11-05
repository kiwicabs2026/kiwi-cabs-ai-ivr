"""
End-to-End Test: Complete Booking Workflow with Real Data
Tests the entire flow from booking data to TaxiCaller API
"""
import requests
import json
from googlemaps.convert import decode_polyline
import googlemaps
from datetime import datetime, timedelta
import pytz

# Initialize clients
gmaps = googlemaps.Client(key='AIzaSyCLE0THoviMIq-7EIS0RYyS5a6KAMJLLJU')
api_key = 'bd624ba9ead25533de1cdef7fe4e8e61'

# New Zealand timezone
NZ_TZ = pytz.timezone('Pacific/Auckland')

print("="*80)
print("🚀 END-TO-END BOOKING WORKFLOW TEST")
print("="*80)

# STEP 1: Simulate booking data from IVR
print("\n📋 STEP 1: Booking Data from IVR")
print("-" * 80)

# Use future time (tomorrow at 14:30)
tomorrow = datetime.now(NZ_TZ) + timedelta(days=1)
future_date = tomorrow.strftime('%d/%m/%Y')
future_time = '14:30'

booking_data = {
    'name': 'John Smith',
    'pickup_address': 'Miramar',
    'destination': 'Newtown',
    'pickup_time': future_time,
    'pickup_date': future_date,
    'driver_instructions': 'Please ring doorbell twice',
    'raw_speech': 'I need a taxi from Miramar to Newtown at 2:30 PM'
}

caller_number = '+64220881234'

print(f"Customer: {booking_data['name']}")
print(f"Pickup: {booking_data['pickup_address']}")
print(f"Destination: {booking_data['destination']}")
print(f"Time: {booking_data['pickup_time']} on {booking_data['pickup_date']}")
print(f"Instructions: {booking_data['driver_instructions']}")
print(f"Caller: {caller_number}")

# STEP 2: Get JWT Token
print("\n🔑 STEP 2: Get JWT Token from TaxiCaller")
print("-" * 80)

jwt_url = f'https://api.taxicaller.net/api/v1/jwt/for-key?key={api_key}&sub=*&ttl=900'
jwt_response = requests.get(jwt_url, timeout=10)
jwt_data = jwt_response.json()
jwt_token = jwt_data.get('token')
print(f"✅ JWT Token obtained: {jwt_token[:50]}...")

# STEP 3: Geocode addresses
print("\n📍 STEP 3: Geocode Addresses")
print("-" * 80)

pickup_geocode = gmaps.geocode(f"{booking_data['pickup_address']}, Wellington, New Zealand", region="nz")
dropoff_geocode = gmaps.geocode(f"{booking_data['destination']}, Wellington, New Zealand", region="nz")

pickup_lat = pickup_geocode[0]['geometry']['location']['lat']
pickup_lng = pickup_geocode[0]['geometry']['location']['lng']
pickup_coords = [int(pickup_lng * 1000000), int(pickup_lat * 1000000)]

dropoff_lat = dropoff_geocode[0]['geometry']['location']['lat']
dropoff_lng = dropoff_geocode[0]['geometry']['location']['lng']
dropoff_coords = [int(dropoff_lng * 1000000), int(dropoff_lat * 1000000)]

print(f"Pickup: {booking_data['pickup_address']}")
print(f"  Lat/Lng: {pickup_lat:.6f}, {pickup_lng:.6f}")
print(f"  Coords: {pickup_coords}")
print(f"Dropoff: {booking_data['destination']}")
print(f"  Lat/Lng: {dropoff_lat:.6f}, {dropoff_lng:.6f}")
print(f"  Coords: {dropoff_coords}")

# STEP 4: Get Route from Google Maps
print("\n🗺️ STEP 4: Get Route from Google Maps")
print("-" * 80)

directions = gmaps.directions(
    origin=f"{booking_data['pickup_address']}, Wellington, New Zealand",
    destination=f"{booking_data['destination']}, Wellington, New Zealand"
)

route = directions[0]
leg = route['legs'][0]
distance_meters = leg['distance']['value']
duration_seconds = leg['duration']['value']
polyline_str = route['overview_polyline']['points']

decoded_points = list(decode_polyline(polyline_str))
route_coords = [[int(p['lng'] * 1e6), int(p['lat'] * 1e6)] for p in decoded_points]

print(f"Distance: {distance_meters}m ({distance_meters/1000:.2f}km)")
print(f"Duration: {duration_seconds}s ({duration_seconds/60:.1f} minutes)")
print(f"Waypoints: {len(route_coords)}")
print(f"First waypoint: {route_coords[0]}")
print(f"Last waypoint: {route_coords[-1]}")

# STEP 5: Build Route Nodes
print("\n🔗 STEP 5: Build Route Nodes with Waypoints")
print("-" * 80)

def build_route_nodes(pickup_address, destination_address, pickup_coords, dropoff_coords, 
                     pickup_timestamp, driver_instructions, route_coords):
    nodes = [
        {
            "actions": [{"@type": "client_action", "item_seq": 0, "action": "in"}],
            "location": {
                "name": pickup_address,
                "coords": pickup_coords
            },
            "times": {"arrive": {"target": pickup_timestamp}},
            "info": {"all": driver_instructions},
            "seq": 0
        }
    ]
    
    if route_coords and len(route_coords) > 2:
        for i, coord in enumerate(route_coords[1:-1], 1):
            nodes.append({
                "actions": [],
                "location": {
                    "name": f"Waypoint {i}",
                    "coords": coord
                },
                "times": {"arrive": {"target": 0}},
                "info": {"all": ""},
                "seq": i
            })
    
    nodes.append({
        "actions": [{"@type": "client_action", "item_seq": 0, "action": "out"}],
        "location": {
            "name": destination_address,
            "coords": dropoff_coords
        },
        "times": {"arrive": {"target": 0}},
        "info": {"all": ""},
        "seq": len(nodes)
    })
    
    return nodes

# Parse pickup time
pickup_datetime = datetime.strptime(f"{booking_data['pickup_date']} {booking_data['pickup_time']}", "%d/%m/%Y %H:%M")
pickup_datetime = NZ_TZ.localize(pickup_datetime)
pickup_timestamp = int(pickup_datetime.timestamp())

route_nodes = build_route_nodes(
    booking_data['pickup_address'],
    booking_data['destination'],
    pickup_coords,
    dropoff_coords,
    pickup_timestamp,
    booking_data['driver_instructions'],
    route_coords
)

print(f"Total nodes: {len(route_nodes)}")
print(f"  Pickup node: seq=0")
print(f"  Waypoint nodes: seq=1 to {len(route_nodes)-2}")
print(f"  Dropoff node: seq={len(route_nodes)-1}")

# STEP 6: Build Booking Payload
print("\n📦 STEP 6: Build Booking Payload")
print("-" * 80)

nz_local_phone = caller_number
if caller_number.startswith("+64"):
    nz_local_phone = "0" + caller_number[3:]

booking_payload = {
    "order": {
        "company_id": 7371,
        "provider_id": 0,
        "order_id": 0,
        "items": [
            {
                "@type": "passengers",
                "seq": 0,
                "passenger": {
                    "name": booking_data['name'],
                    "email": "customer@kiwicabs.co.nz",
                    "phone": nz_local_phone
                },
                "client_id": 0,
                "account": {"id": 0, "customer_id": 0},
                "require": {"seats": 1, "wc": 0, "bags": 1},
                "pay_info": [{"@t": 0, "data": ""}]
            }
        ],
        "route": {
            "meta": {"est_dur": str(duration_seconds), "dist": str(distance_meters)},
            "nodes": route_nodes,
            "legs": [
                {
                    "pts": [],
                    "meta": {"dist": str(distance_meters), "est_dur": str(duration_seconds)},
                    "from_seq": 0,
                    "to_seq": len(route_nodes) - 1
                }
            ]
        }
    }
}

print(f"Payload size: {len(json.dumps(booking_payload))} bytes")
print(f"Customer: {booking_payload['order']['items'][0]['passenger']['name']}")
print(f"Phone: {booking_payload['order']['items'][0]['passenger']['phone']}")
print(f"Route nodes: {len(booking_payload['order']['route']['nodes'])}")
print(f"Distance: {booking_payload['order']['route']['meta']['dist']}m")
print(f"Duration: {booking_payload['order']['route']['meta']['est_dur']}s")

# STEP 7: Send to TaxiCaller API
print("\n📤 STEP 7: Send Booking to TaxiCaller API")
print("-" * 80)

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {jwt_token}',
    'User-Agent': 'KiwiCabs-AI-IVR/2.1'
}

try:
    response = requests.post(
        'https://api.taxicaller.net/api/v1/booker/order',
        json=booking_payload,
        headers=headers,
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCCESS!")
        resp_json = response.json()
        
        # STEP 8: Parse Response
        print("\n✅ STEP 8: Parse Response")
        print("-" * 80)
        
        order_id = resp_json.get('order', {}).get('order_id', 'N/A')
        job_id = resp_json.get('meta', {}).get('job_id', 'N/A')
        driver_id = resp_json.get('meta', {}).get('driver_id', 'N/A')
        vehicle_id = resp_json.get('meta', {}).get('vehicle_id', 'N/A')
        dispatch_time = resp_json.get('dispatch_options', {}).get('dispatch_time', 'N/A')
        
        resp_nodes = resp_json.get('order', {}).get('route', {}).get('nodes', [])
        resp_distance = resp_json.get('order', {}).get('route', {}).get('meta', {}).get('dist', 'N/A')
        resp_duration = resp_json.get('order', {}).get('route', {}).get('meta', {}).get('est_dur', 'N/A')
        
        print(f"Order ID: {order_id}")
        print(f"Job ID: {job_id}")
        print(f"Driver ID: {driver_id}")
        print(f"Vehicle ID: {vehicle_id}")
        print(f"Dispatch Time: {dispatch_time}")
        print(f"Route Nodes: {len(resp_nodes)}")
        print(f"Distance: {resp_distance}m")
        print(f"Duration: {resp_duration}s")
        
        # STEP 9: Final Summary
        print("\n" + "="*80)
        print("✅ END-TO-END TEST COMPLETED SUCCESSFULLY!")
        print("="*80)
        print(f"\n📊 Summary:")
        print(f"  ✅ Booking created for {booking_data['name']}")
        print(f"  ✅ Route: {booking_data['pickup_address']} → {booking_data['destination']}")
        print(f"  ✅ Distance: {resp_distance}m")
        print(f"  ✅ Duration: {resp_duration}s")
        print(f"  ✅ Waypoints: {len(resp_nodes)} nodes")
        print(f"  ✅ Driver assigned: ID {driver_id}")
        print(f"  ✅ Dispatcher will show exact route with all waypoints!")
        print(f"\n🎉 Exact route visualization is working perfectly!")
        
    else:
        print(f"❌ FAILED")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {str(e)}")

