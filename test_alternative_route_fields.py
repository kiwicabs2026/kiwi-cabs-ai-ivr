import requests
import json
from googlemaps.convert import decode_polyline
import googlemaps

# Get JWT token
api_key = 'bd624ba9ead25533de1cdef7fe4e8e61'
jwt_url = f'https://api.taxicaller.net/api/v1/jwt/for-key?key={api_key}&sub=*&ttl=900'

print('🔑 Getting JWT token...')
jwt_response = requests.get(jwt_url, timeout=10)
jwt_data = jwt_response.json()
jwt_token = jwt_data.get('token')

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {jwt_token}',
    'User-Agent': 'KiwiCabs-AI-IVR/2.1'
}

# Get a real polyline from Google Maps
gmaps = googlemaps.Client(key='AIzaSyCLE0THoviMIq-7EIS0RYyS5a6KAMJLLJU')

print('🗺️ Getting route from Google Maps...')
directions = gmaps.directions(
    origin='Miramar, Wellington, New Zealand',
    destination='Newtown, Wellington, New Zealand'
)

if directions:
    route = directions[0]
    leg = route['legs'][0]
    polyline_str = route['overview_polyline']['points']
    
    decoded_points = list(decode_polyline(polyline_str))
    route_coords = [[int(p['lng'] * 1e6), int(p['lat'] * 1e6)] for p in decoded_points]
    
    print(f'📍 Route has {len(decoded_points)} waypoints')
    
    # Test 1: Try adding waypoints to nodes instead of pts
    print(f"\n{'='*70}")
    print(f"📤 Test 1: Add intermediate nodes as waypoints")
    print(f"{'='*70}")
    
    # Create nodes for every 10th waypoint
    nodes = [
        {
            'actions': [{'@type': 'client_action', 'item_seq': 0, 'action': 'in'}],
            'location': {'name': 'Miramar', 'coords': [174813105, -41321728]},
            'times': {'arrive': {'target': 0}},
            'seq': 0
        }
    ]
    
    # Add intermediate waypoints
    for i, coord in enumerate(route_coords[1:-1], 1):
        nodes.append({
            'actions': [],
            'location': {'name': f'Waypoint {i}', 'coords': coord},
            'times': {'arrive': {'target': 0}},
            'seq': i
        })
    
    # Add final node
    nodes.append({
        'actions': [{'@type': 'client_action', 'item_seq': 0, 'action': 'out'}],
        'location': {'name': 'Newtown', 'coords': [174901349, -41210620]},
        'times': {'arrive': {'target': 0}},
        'seq': len(nodes)
    })
    
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
                'nodes': nodes,
                'legs': [
                    {
                        'pts': [],
                        'meta': {'dist': '14385', 'est_dur': '600'},
                        'from_seq': 0,
                        'to_seq': len(nodes) - 1
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
            resp_nodes = resp_json.get('order', {}).get('route', {}).get('nodes', [])
            print(f'Order ID: {order_id}')
            print(f'Nodes in response: {len(resp_nodes)}')
        else:
            print(f'❌ FAILED')
            print(f'Response: {response.text[:300]}')
    except Exception as e:
        print(f'Error: {str(e)}')
    
    # Test 2: Try with legs array having multiple entries (one per segment)
    print(f"\n{'='*70}")
    print(f"📤 Test 2: Multiple legs with waypoints")
    print(f"{'='*70}")
    
    # Create legs for every segment
    legs = []
    for i in range(len(nodes) - 1):
        legs.append({
            'pts': [],
            'meta': {'dist': '1000', 'est_dur': '60'},
            'from_seq': i,
            'to_seq': i + 1
        })
    
    payload['order']['route']['legs'] = legs
    
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
    
    # Test 3: Try with route.meta having additional fields
    print(f"\n{'='*70}")
    print(f"📤 Test 3: Route meta with polyline field")
    print(f"{'='*70}")
    
    payload['order']['route']['legs'] = [
        {
            'pts': [],
            'meta': {'dist': '14385', 'est_dur': '600'},
            'from_seq': 0,
            'to_seq': len(nodes) - 1
        }
    ]
    
    # Try adding polyline to route meta
    payload['order']['route']['polyline'] = polyline_str
    
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

