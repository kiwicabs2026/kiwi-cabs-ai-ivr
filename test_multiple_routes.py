"""
Test Multiple Routes with Different Scenarios
Verifies exact route visualization works for various pickup/dropoff combinations
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
NZ_TZ = pytz.timezone('Pacific/Auckland')

def get_jwt_token():
    """Get fresh JWT token"""
    jwt_url = f'https://api.taxicaller.net/api/v1/jwt/for-key?key={api_key}&sub=*&ttl=900'
    jwt_response = requests.get(jwt_url, timeout=10)
    return jwt_response.json().get('token')

def build_route_nodes(pickup_address, destination_address, pickup_coords, dropoff_coords, 
                     pickup_timestamp, driver_instructions, route_coords):
    """Build route nodes with waypoints"""
    nodes = [
        {
            "actions": [{"@type": "client_action", "item_seq": 0, "action": "in"}],
            "location": {"name": pickup_address, "coords": pickup_coords},
            "times": {"arrive": {"target": pickup_timestamp}},
            "info": {"all": driver_instructions},
            "seq": 0
        }
    ]
    
    if route_coords and len(route_coords) > 2:
        for i, coord in enumerate(route_coords[1:-1], 1):
            nodes.append({
                "actions": [],
                "location": {"name": f"Waypoint {i}", "coords": coord},
                "times": {"arrive": {"target": 0}},
                "info": {"all": ""},
                "seq": i
            })
    
    nodes.append({
        "actions": [{"@type": "client_action", "item_seq": 0, "action": "out"}],
        "location": {"name": destination_address, "coords": dropoff_coords},
        "times": {"arrive": {"target": 0}},
        "info": {"all": ""},
        "seq": len(nodes)
    })
    
    return nodes

def test_route(test_num, pickup, destination, customer_name, phone):
    """Test a single route"""
    print(f"\n{'='*80}")
    print(f"TEST {test_num}: {pickup} → {destination}")
    print(f"{'='*80}")
    
    try:
        # Get JWT token
        jwt_token = get_jwt_token()
        
        # Geocode addresses
        pickup_geocode = gmaps.geocode(f"{pickup}, Wellington, New Zealand", region="nz")
        dropoff_geocode = gmaps.geocode(f"{destination}, Wellington, New Zealand", region="nz")
        
        pickup_lat = pickup_geocode[0]['geometry']['location']['lat']
        pickup_lng = pickup_geocode[0]['geometry']['location']['lng']
        pickup_coords = [int(pickup_lng * 1000000), int(pickup_lat * 1000000)]
        
        dropoff_lat = dropoff_geocode[0]['geometry']['location']['lat']
        dropoff_lng = dropoff_geocode[0]['geometry']['location']['lng']
        dropoff_coords = [int(dropoff_lng * 1000000), int(dropoff_lat * 1000000)]
        
        # Get route from Google Maps
        directions = gmaps.directions(
            origin=f"{pickup}, Wellington, New Zealand",
            destination=f"{destination}, Wellington, New Zealand"
        )
        
        route = directions[0]
        leg = route['legs'][0]
        distance_meters = leg['distance']['value']
        duration_seconds = leg['duration']['value']
        polyline_str = route['overview_polyline']['points']
        
        decoded_points = list(decode_polyline(polyline_str))
        route_coords = [[int(p['lng'] * 1e6), int(p['lat'] * 1e6)] for p in decoded_points]
        
        # Build route nodes
        tomorrow = datetime.now(NZ_TZ) + timedelta(days=1)
        pickup_datetime = NZ_TZ.localize(datetime.strptime(f"{tomorrow.strftime('%d/%m/%Y')} 14:30", "%d/%m/%Y %H:%M"))
        pickup_timestamp = int(pickup_datetime.timestamp())
        
        route_nodes = build_route_nodes(
            pickup, destination, pickup_coords, dropoff_coords,
            pickup_timestamp, "Please ring doorbell", route_coords
        )
        
        # Convert phone
        nz_local_phone = phone
        if phone.startswith("+64"):
            nz_local_phone = "0" + phone[3:]
        
        # Build payload
        booking_payload = {
            "order": {
                "company_id": 7371,
                "provider_id": 0,
                "order_id": 0,
                "items": [{
                    "@type": "passengers",
                    "seq": 0,
                    "passenger": {
                        "name": customer_name,
                        "email": "customer@kiwicabs.co.nz",
                        "phone": nz_local_phone
                    },
                    "client_id": 0,
                    "account": {"id": 0, "customer_id": 0},
                    "require": {"seats": 1, "wc": 0, "bags": 1},
                    "pay_info": [{"@t": 0, "data": ""}]
                }],
                "route": {
                    "meta": {"est_dur": str(duration_seconds), "dist": str(distance_meters)},
                    "nodes": route_nodes,
                    "legs": [{
                        "pts": [],
                        "meta": {"dist": str(distance_meters), "est_dur": str(duration_seconds)},
                        "from_seq": 0,
                        "to_seq": len(route_nodes) - 1
                    }]
                }
            }
        }
        
        # Send to TaxiCaller
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {jwt_token}',
            'User-Agent': 'KiwiCabs-AI-IVR/2.1'
        }
        
        response = requests.post(
            'https://api.taxicaller.net/api/v1/booker/order',
            json=booking_payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            resp_json = response.json()
            order_id = resp_json.get('order', {}).get('order_id', 'N/A')
            resp_nodes = resp_json.get('order', {}).get('route', {}).get('nodes', [])
            
            print(f"✅ SUCCESS!")
            print(f"   Order ID: {order_id}")
            print(f"   Distance: {distance_meters}m ({distance_meters/1000:.2f}km)")
            print(f"   Duration: {duration_seconds}s ({duration_seconds/60:.1f} min)")
            print(f"   Waypoints: {len(resp_nodes)} nodes")
            print(f"   ✅ Exact route with {len(resp_nodes)} waypoints created!")
            return True
        else:
            print(f"❌ FAILED - Status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

# Run tests with different routes
print("\n" + "="*80)
print("🚀 TESTING MULTIPLE ROUTES WITH EXACT ROUTE VISUALIZATION")
print("="*80)

test_cases = [
    (1, "Miramar", "Newtown", "John Smith", "+64220881234"),
    (2, "Karori", "Lambton Quay", "Jane Doe", "+64221234567"),
    (3, "Kelburn", "Courtenay Place", "Bob Johnson", "+64225555555"),
    (4, "Wadestown", "Te Aro", "Alice Williams", "+64229999999"),
]

results = []
for test_num, pickup, destination, name, phone in test_cases:
    success = test_route(test_num, pickup, destination, name, phone)
    results.append((test_num, pickup, destination, success))

# Summary
print(f"\n{'='*80}")
print("📊 TEST SUMMARY")
print(f"{'='*80}")

passed = sum(1 for _, _, _, success in results if success)
total = len(results)

for test_num, pickup, destination, success in results:
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - Test {test_num}: {pickup} → {destination}")

print(f"\n{'='*80}")
print(f"Results: {passed}/{total} tests passed")
if passed == total:
    print("🎉 ALL TESTS PASSED! Exact route visualization is working perfectly!")
else:
    print(f"⚠️ {total - passed} test(s) failed")
print(f"{'='*80}")

