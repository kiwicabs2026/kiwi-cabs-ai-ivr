import requests
import json

# Get JWT token
api_key = 'bd624ba9ead25533de1cdef7fe4e8e61'
jwt_url = f'https://api.taxicaller.net/api/v1/jwt/for-key?key={api_key}&sub=*&ttl=900'

print('🔑 Getting JWT token...')
jwt_response = requests.get(jwt_url, timeout=10)
jwt_data = jwt_response.json()
jwt_token = jwt_data.get('token')
print(f'✅ JWT Token obtained: {jwt_token[:50]}...')

# Test different payload variations
test_payloads = [
    {
        'name': 'Test 1: Minimal - no route',
        'payload': {
            'order': {
                'company_id': 7371,
                'provider_id': 0,
                'order_id': 0,
                'items': [
                    {
                        '@type': 'passengers',
                        'seq': 0,
                        'passenger': {
                            'name': 'Test',
                            'email': 'test@test.com',
                            'phone': '0220881234'
                        },
                        'client_id': 0,
                        'account': {
                            'id': 0,
                            'customer_id': 0
                        },
                        'require': {
                            'seats': 1,
                            'wc': 0,
                            'bags': 1
                        },
                        'pay_info': [
                            {
                                '@t': 0,
                                'data': ''
                            }
                        ]
                    }
                ]
            }
        }
    },
    {
        'name': 'Test 2: With empty route',
        'payload': {
            'order': {
                'company_id': 7371,
                'provider_id': 0,
                'order_id': 0,
                'items': [
                    {
                        '@type': 'passengers',
                        'seq': 0,
                        'passenger': {
                            'name': 'Test',
                            'email': 'test@test.com',
                            'phone': '0220881234'
                        },
                        'client_id': 0,
                        'account': {
                            'id': 0,
                            'customer_id': 0
                        },
                        'require': {
                            'seats': 1,
                            'wc': 0,
                            'bags': 1
                        },
                        'pay_info': [
                            {
                                '@t': 0,
                                'data': ''
                            }
                        ]
                    }
                ],
                'route': {}
            }
        }
    },
    {
        'name': 'Test 3: With route meta only',
        'payload': {
            'order': {
                'company_id': 7371,
                'provider_id': 0,
                'order_id': 0,
                'items': [
                    {
                        '@type': 'passengers',
                        'seq': 0,
                        'passenger': {
                            'name': 'Test',
                            'email': 'test@test.com',
                            'phone': '0220881234'
                        },
                        'client_id': 0,
                        'account': {
                            'id': 0,
                            'customer_id': 0
                        },
                        'require': {
                            'seats': 1,
                            'wc': 0,
                            'bags': 1
                        },
                        'pay_info': [
                            {
                                '@t': 0,
                                'data': ''
                            }
                        ]
                    }
                ],
                'route': {
                    'meta': {
                        'est_dur': '600',
                        'dist': '5000'
                    }
                }
            }
        }
    },
    {
        'name': 'Test 4: With route meta and nodes',
        'payload': {
            'order': {
                'company_id': 7371,
                'provider_id': 0,
                'order_id': 0,
                'items': [
                    {
                        '@type': 'passengers',
                        'seq': 0,
                        'passenger': {
                            'name': 'Test',
                            'email': 'test@test.com',
                            'phone': '0220881234'
                        },
                        'client_id': 0,
                        'account': {
                            'id': 0,
                            'customer_id': 0
                        },
                        'require': {
                            'seats': 1,
                            'wc': 0,
                            'bags': 1
                        },
                        'pay_info': [
                            {
                                '@t': 0,
                                'data': ''
                            }
                        ]
                    }
                ],
                'route': {
                    'meta': {
                        'est_dur': '600',
                        'dist': '5000'
                    },
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
                    ]
                }
            }
        }
    }
]

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {jwt_token}',
    'User-Agent': 'KiwiCabs-AI-IVR/2.1'
}

for test in test_payloads:
    print(f"\n{'='*60}")
    print(f"📤 {test['name']}")
    print(f"{'='*60}")
    try:
        response = requests.post(
            'https://api.taxicaller.net/api/v1/booker/order',
            json=test['payload'],
            headers=headers,
            timeout=10
        )
        print(f'Status: {response.status_code}')
        print(f'Response: {response.text}')
    except Exception as e:
        print(f'Error: {str(e)}')

