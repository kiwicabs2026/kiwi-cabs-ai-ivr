import requests
import time

# Step 1: Get Bearer token dynamically
key = "c18afde179ec057037084b4daf10f01a"
sub = "*"

token_url = f"https://api-rc.taxicaller.net/api/v1/jwt/for-key?key={key}&sub={sub}"

response = requests.get(token_url)
if response.status_code == 200:
    token_data = response.json()
    bearer_token = token_data.get("token")  # Assuming response JSON has {"token": "eyJ..."}
    if not bearer_token:
        raise ValueError("Token not found in response")
else:
    raise Exception(f"Failed to get token: {response.status_code} {response.text}")

# Step 2: Use token to make booking

url = "https://api-rc.taxicaller.net/api/v1/booker/order"

headers = {
    "Authorization": f"Bearer {bearer_token}",
    "Content-Type": "application/json"
}

future_timestamp = int(time.time()) + 30 * 60  # 30 minutes from now

payload = {
    "order": {
        "company_id": 8257,
        "provider_id": 12345,
        "items": [
            {
                "@type": "passengers",
                "seq": 0,
                "passenger": {
                    "name": "raj baba",
                    "phone": "+46721234567",
                    "email": "john@example.com"
                },
                "client_id": 42,
                "account": {
                    "id": 0,
                    "extra": None
                },
                "require": {
                    "seats": 1,
                    "wc": 0,
                    "bags": 1
                },
                "pay_info": [
                    {
                        "@t": 0,
                        "data": None
                    }
                ],
                "custom_fields": {
                    "tag.driver.1": "true",
                    "tag.vehicle.1": "true"
                }
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
                        "name": "Järnvägsgatan 3, 582 22 Linköping, Sweden",
                        "coords": [15626493, 58415701]
                    },
                    "times": {
                        "arrive": {
                            "target": future_timestamp,
                            "latest": 0
                        }
                    },
                    "info": {
                        "all": "Needs help with luggage"
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
                        "name": "Teknikringen 1A, Linköping, Sweden",
                        "coords": [15566656, 58393584]
                    },
                    "times": None,
                    "info": {},
                    "seq": 1
                }
            ],
            "legs": [
                {
                    "meta": {
                        "dist": 5496,
                        "est_dur": 603
                    },
                    "pts": [
                        15621480, 58410380, 15619850, 58410130,
                        15620170, 58409480, 15618970, 58409330,
                        15618900, 58409300, 15618800, 58409240,
                        15618610, 58408880, 15618220, 58408300,
                        15618090, 58408170, 15617930, 58408070
                    ],
                    "from_seq": 0,
                    "to_seq": 1
                }
            ],
            "meta": {
                "dist": 6264,
                "est_dur": 683
            }
        }
    }
}

response = requests.post(url, headers=headers, json=payload)

print("Booking Status Code:", response.status_code)
print("Booking Response Body:", response.text)