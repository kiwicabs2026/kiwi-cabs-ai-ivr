import requests
import json
from googlemaps.convert import decode_polyline

# Get JWT token
api_key = 'bd624ba9ead25533de1cdef7fe4e8e61'
jwt_url = f'https://api.taxicaller.net/api/v1/jwt/for-key?key={api_key}&sub=*&ttl=900'

print('🔑 Getting JWT token...')
jwt_response = requests.get(jwt_url, timeout=10)
jwt_data = jwt_response.json()
jwt_token = jwt_data.get('token')
print(f'✅ JWT Token obtained')

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {jwt_token}',
    'User-Agent': 'KiwiCabs-AI-IVR/2.1'
}

# Get a real polyline from Google Maps
import googlemaps
gmaps = googlemaps.Client(key='AIzaSyCLE0THoviMIq-7EIS0RYyS5a6KAMJLLJU')

print('\n🗺️ Getting route from Google Maps...')
directions = gmaps.directions(
    origin='Miramar, Wellington, New Zealand',
    destination='Newtown, Wellington, New Zealand'
)

if directions:
    polyline_str = directions[0]['overview_polyline']['points']
    print(f'📍 Polyline string: {polyline_str[:50]}...')
    
    # Decode it
    decoded_points = list(decode_polyline(polyline_str))
    print(f'📍 Decoded {len(decoded_points)} points')
    print(f'📍 First point: {decoded_points[0]}')
    print(f'📍 Last point: {decoded_points[-1]}')
    
    # Convert to TaxiCaller format
    route_coords = [[int(p['lng'] * 1e6), int(p['lat'] * 1e6)] for p in decoded_points]
    print(f'📍 Converted to TaxiCaller format: {len(route_coords)} points')
    print(f'📍 First coord: {route_coords[0]}')
    print(f'📍 Last coord: {route_coords[-1]}')
    
    # Test 1: Send with full polyline
    print(f"\n{'='*70}")
    print(f"📤 Test 1: Full polyline ({len(route_coords)} points)")
    print(f"{'='*70}")
    
    payload = {
        'order': {
            'company_id': 7371,
            'provider_id': 0,
            'order_id': 0,
            'items': [
                {
                    '@type': 'passengers',
                    'seq': 0,
                    'passenger': {'name': 'Test', 'email': 'test@test.com', 'phone': '0220881234'},
                    'client_id': 0,
                    'account': {'id': 0, 'customer_id': 0},
                    'require': {'seats': 1, 'wc': 0, 'bags': 1},
                    'pay_info': [{'@t': 0, 'data': ''}]
                }
            ],
            'route': {
                'meta': {'est_dur': '600', 'dist': '14385'},
                'nodes': [
                    {
                        'actions': [{'@type': 'client_action', 'item_seq': 0, 'action': 'in'}],
                        'location': {'name': 'Miramar', 'coords': [174813105, -41321728]},
                        'times': {'arrive': {'target': 0}},
                        'seq': 0
                    },
                    {
                        'actions': [{'@type': 'client_action', 'item_seq': 0, 'action': 'out'}],
                        'location': {'name': 'Newtown', 'coords': [174901349, -41210620]},
                        'times': {'arrive': {'target': 0}},
                        'seq': 1
                    }
                ],
                'legs': [
                    {
                        'pts': route_coords,
                        'meta': {'dist': '14385', 'est_dur': '600'},
                        'from_seq': 0,
                        'to_seq': 1
                    }
                ]
            }
        }
    }
    
    try:
        response = requests.post(
            'https://api.taxicaller.net/api/v1/booker/order',
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f'Status: {response.status_code}')
        if response.status_code == 200:
            print(f'✅ SUCCESS!')
            resp_json = response.json()
            order_id = resp_json.get('order', {}).get('order_id', 'N/A')
            pts_in_response = resp_json.get('order', {}).get('route', {}).get('legs', [{}])[0].get('pts', [])
            print(f'Order ID: {order_id}')
            print(f'pts in response: {len(pts_in_response)} waypoints')
        else:
            print(f'❌ FAILED')
            print(f'Response: {response.text[:300]}')
    except Exception as e:
        print(f'Error: {str(e)}')
    
    # Test 2: Send with decimals (not integers)
    print(f"\n{'='*70}")
    print(f"📤 Test 2: Polyline with decimal coordinates")
    print(f"{'='*70}")
    
    route_coords_decimal = [[p['lng'], p['lat']] for p in decoded_points]
    
    payload['order']['route']['legs'][0]['pts'] = route_coords_decimal
    
    try:
        response = requests.post(
            'https://api.taxicaller.net/api/v1/booker/order',
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f'Status: {response.status_code}')
        if response.status_code == 200:
            print(f'✅ SUCCESS!')
        else:
            print(f'❌ FAILED')
            print(f'Response: {response.text[:300]}')
    except Exception as e:
        print(f'Error: {str(e)}')
    
    # Test 3: Send with compressed polyline string
    print(f"\n{'='*70}")
    print(f"📤 Test 3: Compressed polyline string")
    print(f"{'='*70}")
    
    payload['order']['route']['legs'][0]['pts'] = polyline_str
    
    try:
        response = requests.post(
            'https://api.taxicaller.net/api/v1/booker/order',
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f'Status: {response.status_code}')
        if response.status_code == 200:
            print(f'✅ SUCCESS!')
        else:
            print(f'❌ FAILED')
            print(f'Response: {response.text[:300]}')
    except Exception as e:
        print(f'Error: {str(e)}')

