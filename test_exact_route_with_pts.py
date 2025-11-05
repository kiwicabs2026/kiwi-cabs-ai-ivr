#!/usr/bin/env python3
"""
Test exact route implementation with real Google Maps data and flattened pts array.

This test verifies that:
1. Google Maps polyline is correctly decoded
2. Coordinates are converted to TaxiCaller format [lng*1e6, lat*1e6]
3. pts array is flattened: [lng1, lat1, lng2, lat2, ...]
4. Booking is successfully created with exact route visualization
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
import pytz

try:
    import googlemaps
    from googlemaps.convert import decode_polyline
except ImportError:
    print("❌ googlemaps not installed. Install with: pip install googlemaps")
    sys.exit(1)

# Credentials
TAXICALLER_API_KEY = "bd624ba9ead25533de1cdef7fe4e8e61"
COMPANY_ID = 7371
GOOGLE_MAPS_API_KEY = "AIzaSyCLE0THoviMIq-7EIS0RYyS5a6KAMJLLJU"

NZ_TZ = pytz.timezone('Pacific/Auckland')

# Initialize Google Maps client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

def get_taxicaller_jwt():
    """Get JWT token from TaxiCaller API"""
    try:
        url = f"https://api.taxicaller.net/api/v1/jwt/for-key?key={TAXICALLER_API_KEY}&sub=*&ttl=900"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('token', '')
        return None
    except Exception as e:
        print(f"❌ Error getting JWT: {e}")
        return None

def get_route_with_polyline(pickup_address, destination_address):
    """Get route with polyline from Google Maps"""
    try:
        pickup_full = f"{pickup_address}, Wellington, New Zealand"
        destination_full = f"{destination_address}, Wellington, New Zealand"
        
        print(f"📍 Getting route: {pickup_full} → {destination_full}")
        
        directions = gmaps.directions(
            origin=pickup_full,
            destination=destination_full,
            mode="driving",
            region="nz"
        )
        
        if not directions or len(directions) == 0:
            print("❌ No route found")
            return None, None, None
        
        route = directions[0]
        leg = route['legs'][0]
        
        distance_meters = leg['distance']['value']
        duration_seconds = leg['duration']['value']
        
        # Extract polyline
        polyline_str = route.get('overview_polyline', {}).get('points', '')
        
        if not polyline_str:
            print("❌ No polyline in response")
            return distance_meters, duration_seconds, []
        
        # Decode polyline and convert to TaxiCaller format
        decoded_points = list(decode_polyline(polyline_str))
        print(f"✅ Decoded {len(decoded_points)} polyline points")
        
        route_coords = []
        for point in decoded_points:
            if isinstance(point, dict):
                lat = point.get('lat', 0)
                lng = point.get('lng', 0)
            elif isinstance(point, (tuple, list)) and len(point) >= 2:
                lat, lng = point[0], point[1]
            else:
                continue
            
            if lat != 0 or lng != 0:
                route_coords.append([int(lng * 1e6), int(lat * 1e6)])
        
        print(f"✅ Converted to {len(route_coords)} TaxiCaller coordinates")
        
        return distance_meters, duration_seconds, route_coords
        
    except Exception as e:
        print(f"❌ Error getting route: {e}")
        return None, None, None

def test_exact_route(pickup_address, destination_address):
    """Test exact route with real Google Maps data"""
    
    print("=" * 80)
    print(f"🧪 TEST: {pickup_address} → {destination_address}")
    print("=" * 80)
    
    # Get JWT token
    jwt_token = get_taxicaller_jwt()
    if not jwt_token:
        print("❌ Failed to get JWT token")
        return False
    
    print(f"✅ Got JWT token")
    
    # Get route from Google Maps
    distance_meters, duration_seconds, route_coords = get_route_with_polyline(
        pickup_address, destination_address
    )
    
    if not route_coords:
        print("❌ Failed to get route")
        return False
    
    print(f"📊 Route Info:")
    print(f"   Distance: {distance_meters}m ({distance_meters/1000:.2f}km)")
    print(f"   Duration: {duration_seconds}s ({duration_seconds/60:.1f} min)")
    print(f"   Waypoints: {len(route_coords)}")
    
    # Convert to flattened pts array
    pts_array = []
    for coord in route_coords:
        pts_array.append(coord[0])  # lng
        pts_array.append(coord[1])  # lat
    
    print(f"📊 PTS Array:")
    print(f"   Format: [lng1, lat1, lng2, lat2, ...]")
    print(f"   Length: {len(pts_array)} values ({len(pts_array)//2} coordinate pairs)")
    
    # Create booking payload
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
                "meta": {"est_dur": str(duration_seconds), "dist": str(distance_meters)},
                "nodes": [
                    {
                        "actions": [{"@type": "client_action", "item_seq": 0, "action": "in"}],
                        "location": {
                            "name": pickup_address,
                            "coords": route_coords[0]
                        },
                        "times": {"arrive": {"target": pickup_time}},
                        "info": {"all": "Test booking"},
                        "seq": 0
                    },
                    {
                        "actions": [{"@type": "client_action", "item_seq": 0, "action": "out"}],
                        "location": {
                            "name": destination_address,
                            "coords": route_coords[-1]
                        },
                        "times": None,
                        "info": {"all": ""},
                        "seq": 1
                    }
                ],
                "legs": [
                    {
                        "pts": pts_array,  # ✅ Flattened array format
                        "meta": {"dist": str(distance_meters), "est_dur": str(duration_seconds)},
                        "from_seq": 0,
                        "to_seq": 1
                    }
                ]
            }
        }
    }
    
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
            order_id = data.get('order', {}).get('order_id', 'N/A')
            print(f"✅ SUCCESS! Booking created!")
            print(f"   Order ID: {order_id}")
            print(f"   PTS array: {len(pts_array)} values ({len(pts_array)//2} waypoints)")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text[:300]}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending booking: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 EXACT ROUTE IMPLEMENTATION TEST")
    print("Testing with real Google Maps data and flattened pts array")
    print("=" * 80 + "\n")
    
    test_routes = [
        ("Miramar", "Newtown"),
        ("Karori", "Lambton Quay"),
        ("Kelburn", "Courtenay Place"),
    ]
    
    results = []
    for pickup, destination in test_routes:
        success = test_exact_route(pickup, destination)
        results.append((f"{pickup} → {destination}", success))
        print()
    
    # Summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for route, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {route}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Exact route implementation is working!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)

