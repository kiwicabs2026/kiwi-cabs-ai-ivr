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

# Test different pts formats
test_payloads = [
    {
        'name': 'Test 1: pts with 3 waypoints (integers)',
        'payload': {
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
                            'pts': [[174813105, -41321728], [174857227, -41316019], [174901349, -41210620]],
                            'meta': {'dist': '5000', 'est_dur': '600'},
                            'from_seq': 0,
                            'to_seq': 1
                        }
                    ]
                }
            }
        }
    },
    {
        'name': 'Test 2: pts with lat/lng objects',
        'payload': {
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
                            'pts': [
                                {'lat': -41.321728, 'lng': 174.813105},
                                {'lat': -41.316019, 'lng': 174.857227},
                                {'lat': -41.210620, 'lng': 174.901349}
                            ],
                            'meta': {'dist': '5000', 'est_dur': '600'},
                            'from_seq': 0,
                            'to_seq': 1
                        }
                    ]
                }
            }
        }
    },
    {
        'name': 'Test 3: pts with many waypoints (integers)',
        'payload': {
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
                            'pts': [
                                [174813105, -41321728],
                                [174815000, -41321500],
                                [174820000, -41320000],
                                [174830000, -41318000],
                                [174840000, -41315000],
                                [174850000, -41312000],
                                [174860000, -41311000],
                                [174870000, -41312000],
                                [174880000, -41313000],
                                [174890000, -41211000],
                                [174901349, -41210620]
                            ],
                            'meta': {'dist': '5000', 'est_dur': '600'},
                            'from_seq': 0,
                            'to_seq': 1
                        }
                    ]
                }
            }
        }
    }
]

for test in test_payloads:
    print(f"\n{'='*70}")
    print(f"📤 {test['name']}")
    print(f"{'='*70}")
    try:
        response = requests.post(
            'https://api.taxicaller.net/api/v1/booker/order',
            json=test['payload'],
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
                if pts_in_response:
                    print(f'  First pt: {pts_in_response[0]}')
                    print(f'  Last pt: {pts_in_response[-1]}')
            except Exception as e:
                print(f'Could not parse response: {e}')
        else:
            print(f'❌ FAILED')
            print(f'Response: {response.text[:300]}')
    except Exception as e:
        print(f'Error: {str(e)}')

