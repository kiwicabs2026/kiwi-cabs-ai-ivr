#!/usr/bin/env python3
"""
Test to verify pts array is correctly formatted as flattened coordinates
according to TaxiCaller API documentation.

pts should be: [lng1, lat1, lng2, lat2, lng3, lat3, ...]
NOT: [[lng1, lat1], [lng2, lat2], [lng3, lat3], ...]
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Environment variables (from user's provided credentials)
TAXICALLER_API_KEY = "bd624ba9ead25533de1cdef7fe4e8e61"
COMPANY_ID = 7371
GOOGLE_MAPS_API_KEY = "AIzaSyCLE0THoviMIq-7EIS0RYyS5a6KAMJLLJU"

NZ_TZ = pytz.timezone('Pacific/Auckland')

def get_taxicaller_jwt():
    """Get JWT token from TaxiCaller API"""
    try:
        url = f"https://api.taxicaller.net/api/v1/jwt/for-key?key={TAXICALLER_API_KEY}&sub=*&ttl=900"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # The response has 'token' key, not 'jwt'
            return data.get('token', '')
        else:
            print(f"❌ Failed to get JWT: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting JWT: {e}")
        return None

def test_pts_array_format():
    """Test that pts array is correctly formatted as flattened coordinates"""
    
    print("=" * 80)
    print("🧪 TEST: PTS Array Format (Flattened Coordinates)")
    print("=" * 80)
    
    # Get JWT token
    jwt_token = get_taxicaller_jwt()
    if not jwt_token:
        print("❌ Failed to get JWT token")
        return False
    
    print(f"✅ Got JWT token: {jwt_token[:20]}...")
    
    # Create test route coordinates (simulating Google Maps polyline)
    # These are in [lng*1e6, lat*1e6] format
    route_coords = [
        [174813170, -41321550],  # Pickup: Miramar
        [174812000, -41320000],  # Waypoint 1
        [174811000, -41319000],  # Waypoint 2
        [174810000, -41318000],  # Waypoint 3
        [174809000, -41317000],  # Waypoint 4
        [174808170, -41316550],  # Dropoff: Newtown
    ]
    
    # Convert to flattened pts array: [lng1, lat1, lng2, lat2, ...]
    pts_array = []
    for coord in route_coords:
        pts_array.append(coord[0])  # lng
        pts_array.append(coord[1])  # lat
    
    print(f"\n📍 Route Coordinates:")
    print(f"   Input format: [[lng*1e6, lat*1e6], ...]")
    print(f"   Number of waypoints: {len(route_coords)}")
    print(f"   First waypoint: {route_coords[0]}")
    print(f"   Last waypoint: {route_coords[-1]}")
    
    print(f"\n📊 PTS Array (Flattened):")
    print(f"   Format: [lng1, lat1, lng2, lat2, ...]")
    print(f"   Length: {len(pts_array)} values ({len(pts_array)//2} coordinate pairs)")
    print(f"   First 4 values: {pts_array[:4]}")
    print(f"   Last 4 values: {pts_array[-4:]}")
    
    # Verify format
    if len(pts_array) % 2 != 0:
        print(f"❌ ERROR: pts_array has odd number of values! Length: {len(pts_array)}")
        return False
    
    print(f"✅ pts_array has even number of values (correct format)")
    
    # Create booking payload with flattened pts array
    tomorrow = datetime.now(NZ_TZ) + timedelta(days=1)
    pickup_time = int(tomorrow.replace(hour=14, minute=30, second=0, microsecond=0).timestamp())
    
    booking_payload = {
        "order": {
            "company_id": COMPANY_ID,
            "provider_id": 0,
            "order_id": 0,
            "items": [
                {
                    "@type": "passengers",
                    "seq": 0,
                    "passenger": {
                        "name": "Test User",
                        "email": "test@example.com",
                        "phone": "0220881234"
                    },
                    "client_id": 0,
                    "account": {"id": 0, "customer_id": 0},
                    "require": {"seats": 1, "wc": 0, "bags": 1},
                    "pay_info": [{"@t": 0, "data": ""}]
                }
            ],
            "route": {
                "meta": {"est_dur": "600", "dist": "4386"},
                "nodes": [
                    {
                        "actions": [{"@type": "client_action", "item_seq": 0, "action": "in"}],
                        "location": {
                            "name": "Miramar, Wellington",
                            "coords": [174813170, -41321550]
                        },
                        "times": {"arrive": {"target": pickup_time}},
                        "info": {"all": "Test booking"},
                        "seq": 0
                    },
                    {
                        "actions": [{"@type": "client_action", "item_seq": 0, "action": "out"}],
                        "location": {
                            "name": "Newtown, Wellington",
                            "coords": [174808170, -41316550]
                        },
                        "times": None,
                        "info": {"all": ""},
                        "seq": 1
                    }
                ],
                "legs": [
                    {
                        "pts": pts_array,  # ✅ Flattened array format
                        "meta": {"dist": "4386", "est_dur": "600"},
                        "from_seq": 0,
                        "to_seq": 1
                    }
                ]
            }
        }
    }
    
    print(f"\n📦 Booking Payload:")
    print(f"   Nodes: {len(booking_payload['order']['route']['nodes'])}")
    print(f"   Legs: {len(booking_payload['order']['route']['legs'])}")
    print(f"   PTS in leg: {len(booking_payload['order']['route']['legs'][0]['pts'])} values")
    
    # Send to TaxiCaller API
    print(f"\n🚀 Sending booking to TaxiCaller API...")
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            "https://api.taxicaller.net/api/v1/booker/order",
            json=booking_payload,
            headers=headers,
            timeout=10
        )
        
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS! Booking created!")
            print(f"   Order ID: {data.get('order', {}).get('order_id', 'N/A')}")
            print(f"   Job ID: {data.get('order', {}).get('job_id', 'N/A')}")
            print(f"\n✅ PTS array format is CORRECT!")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending booking: {e}")
        return False

if __name__ == "__main__":
    success = test_pts_array_format()
    sys.exit(0 if success else 1)

