import requests
import json

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

# Test with empty pts array
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
            'meta': {'est_dur': '600', 'dist': '5000'},
            'nodes': [
                {
                    'actions': [{'@type': 'client_action', 'item_seq': 0, 'action': 'in'}],
                    'location': {'name': 'Start', 'coords': [174813105, -41321728]},
                    'times': {'arrive': {'target': 0}},
                    'seq': 0
                },
                {
                    'actions': [{'@type': 'client_action', 'item_seq': 0, 'action': 'out'}],
                    'location': {'name': 'End', 'coords': [174901349, -41210620]},
                    'times': {'arrive': {'target': 0}},
                    'seq': 1
                }
            ],
            'legs': [
                {
                    'pts': [],  # Empty array
                    'meta': {'dist': '5000', 'est_dur': '600'},
                    'from_seq': 0,
                    'to_seq': 1
                }
            ]
        }
    }
}

print(f"\n{'='*70}")
print(f"📤 Test: pts with empty array")
print(f"{'='*70}")
try:
    response = requests.post(
        'https://api.taxicaller.net/api/v1/booker/order',
        json=payload,
        headers=headers,
        timeout=10
    )
    print(f'Status: {response.status_code}')
    if response.status_code == 200:
        print(f'✅ SUCCESS - Booking created!')
        try:
            resp_json = response.json()
            order_id = resp_json.get('order', {}).get('order_id', 'N/A')
            pts_in_response = resp_json.get('order', {}).get('route', {}).get('legs', [{}])[0].get('pts', [])
            print(f'Order ID: {order_id}')
            print(f'pts in response: {len(pts_in_response)} waypoints')
            print(f'Full response (first 500 chars): {json.dumps(resp_json, indent=2)[:500]}')
        except Exception as e:
            print(f'Could not parse response: {e}')
    else:
        print(f'❌ FAILED')
        print(f'Response: {response.text}')
except Exception as e:
    print(f'Error: {str(e)}')

