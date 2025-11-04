# 🔍 Debugging TaxiCaller 500 NullPointerException

## Problem
TaxiCaller is still returning 500 NullPointerException even after:
- ✅ Adding `"times"` field to dropoff node
- ✅ Adding `"info"` field to dropoff node
- ✅ Fixing polyline decoding (355 waypoints)
- ✅ Validating coordinates

---

## What We Know

### ✅ Working
- Polyline decoding: 355 points decoded and converted
- Coordinates: Valid [lng*1e6, lat*1e6] format
- Route data: 23939m, 1552s
- Payload JSON: Valid JSON (9509 bytes)

### ❌ Still Failing
- TaxiCaller API returns 500 NullPointerException
- Error happens after Bearer token is sent
- Payload structure seems correct

---

## Debug Output Added

### 1. Booking Data Debug (Line 1005-1013)
```python
print(f"🔍 DEBUG - booking_data keys: {list(booking_data.keys())}")
print(f"🔍 DEBUG - booking_data['name']: {booking_data.get('name', 'MISSING')}")
print(f"🔍 DEBUG - booking_data['pickup_address']: {booking_data.get('pickup_address', 'MISSING')}")
print(f"🔍 DEBUG - booking_data['destination']: {booking_data.get('destination', 'MISSING')}")
print(f"🔍 DEBUG - booking_data['driver_instructions']: {booking_data.get('driver_instructions', 'MISSING')}")
```

**Purpose:** Verify all required fields are present in booking_data

---

### 2. PTS Field Debug (Line 1116-1134)
```python
pts_field = booking_payload['order']['route']['legs'][0]['pts']
print(f"🔍 DEBUG - pts field type: {type(pts_field)}")
print(f"🔍 DEBUG - pts field length: {len(pts_field)}")
if pts_field:
    print(f"🔍 DEBUG - pts[0]: {pts_field[0]}")
    print(f"🔍 DEBUG - pts[0] type: {type(pts_field[0])}")

# Print full payload for debugging
print(f"📋 FULL PAYLOAD:\n{json.dumps(booking_payload, indent=2)}")
```

**Purpose:** See the exact structure of the payload being sent

---

## What to Look For

After restart, check console for:

1. **Booking Data Debug**
   ```
   🔍 DEBUG - booking_data keys: ['name', 'pickup_address', 'destination', ...]
   🔍 DEBUG - booking_data['name']: Donald Trump
   🔍 DEBUG - booking_data['pickup_address']: 63 Hobart Street, Miramar, Wellington 6003, New Zealand
   🔍 DEBUG - booking_data['destination']: 638 High Street, Boulcott, Lower Hutt 5010, New Zealand
   🔍 DEBUG - booking_data['driver_instructions']: MISSING or actual value
   ```

2. **PTS Field Debug**
   ```
   🔍 DEBUG - pts field type: <class 'list'>
   🔍 DEBUG - pts field length: 355
   🔍 DEBUG - pts[0]: [174813170, -41321550]
   🔍 DEBUG - pts[0] type: <class 'list'>
   ```

3. **Full Payload**
   - Look for any `null` values in JSON
   - Look for any empty strings where values should be
   - Look for any missing fields

---

## Possible Issues to Check

1. **Null values in payload**
   - `"name": null` instead of `"name": "Donald Trump"`
   - `"email": null` instead of `"email": "customer@kiwicabs.co.nz"`
   - `"phone": null` instead of `"phone": "0220881234"`

2. **Empty or missing fields**
   - `"pickup_address": ""` (empty string)
   - `"destination": ""` (empty string)
   - `"driver_instructions": ""` (empty string)

3. **Coordinate issues**
   - `"coords": [0, 0]` (invalid coordinates)
   - `"coords": null` (null coordinates)
   - `"coords": []` (empty coordinates)

4. **PTS field issues**
   - `"pts": []` (empty waypoints)
   - `"pts": null` (null waypoints)
   - `"pts": [[0, 0], [0, 0]]` (invalid waypoints)

5. **Times field issues**
   - `"target": null` (null timestamp)
   - `"target": "0"` (string instead of number)

---

## Next Steps

1. **Restart the server**
2. **Create a new booking**
3. **Check console output** for the debug messages
4. **Look for any null or empty values** in the full payload
5. **Report back** with the debug output

---

## Expected Console Output

```
🔍 DEBUG - booking_data keys: ['name', 'pickup_address', 'destination', 'pickup_time', 'pickup_date', 'driver_instructions', 'customer_name']
🔍 DEBUG - booking_data['name']: Donald Trump
🔍 DEBUG - booking_data['pickup_address']: 63 Hobart Street, Miramar, Wellington 6003, New Zealand
🔍 DEBUG - booking_data['destination']: 638 High Street, Boulcott, Lower Hutt 5010, New Zealand
🔍 DEBUG - booking_data['driver_instructions']: MISSING
🔍 DEBUG - pts field type: <class 'list'>
🔍 DEBUG - pts field length: 355
🔍 DEBUG - pts[0]: [174813170, -41321550]
🔍 DEBUG - pts[0] type: <class 'list'>
📋 FULL PAYLOAD:
{
  "order": {
    "company_id": 7371,
    "provider_id": 0,
    "items": [
      {
        "@type": "passengers",
        "seq": 0,
        "passenger": {
          "name": "Donald Trump",
          "email": "customer@kiwicabs.co.nz",
          "phone": "0220881234"
        },
        ...
      }
    ],
    ...
  }
}
```

---

## Status

🔍 **DEBUGGING** - Waiting for console output to identify the null value

Once we see the full payload, we can identify exactly which field is causing the NullPointerException.

