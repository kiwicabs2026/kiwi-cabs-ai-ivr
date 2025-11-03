# 🚖 TaxiCaller Route Distance, Duration & Polyline Fix

## Problem
TaxiCaller support reported that the IVR system was sending bookings with **hardcoded distance and duration values** (5000m and 600 seconds) for every booking. Additionally, the route path (polyline) was missing, showing only start and end points instead of the actual route.

**TaxiCaller's Response:**
> "Our system simply displays what it received in the request; it doesn't calculate the route, distance, or duration automatically. That information needs to come in the request. For the exact route path on the dispatcher map, include the polyline coordinates."

---

## Solution Implemented

### 1. New Function: `decode_polyline()`
Added a helper function to decode Google Maps polyline strings to coordinate pairs:

```python
def decode_polyline(polyline_str):
    """
    Decode Google Maps polyline string to list of [lng*1e6, lat*1e6] coordinates
    """
```

**Features:**
- Decodes compressed polyline format from Google Maps
- Returns coordinates as [lng*1e6, lat*1e6] pairs (TaxiCaller format)
- Handles errors gracefully

### 2. Enhanced Function: `get_route_distance_and_duration()`
Updated to return distance, duration, AND route polyline:

```python
def get_route_distance_and_duration(pickup_address, destination_address):
    """
    Get actual distance, duration, and route polyline from Google Maps Directions API
    Returns: (distance_in_meters, duration_in_seconds, route_coordinates_list)
    """
```

**Features:**
- Uses Google Maps Directions API (already configured in the app)
- Returns actual distance in meters
- Returns actual duration in seconds
- Returns full route polyline as list of [lng*1e6, lat*1e6] coordinates
- Falls back to defaults (5000m, 600s, []) if Google Maps is unavailable
- Adds Wellington context automatically

### 3. Updated Booking Payload
Modified `send_booking_to_taxicaller()` to use actual route data in **TWO places**:

**Location 1 - Route Meta (line 1023):**
```python
"route": {
    "meta": {"est_dur": str(duration_seconds), "dist": str(distance_meters)},  # Actual values!
    ...
}
```

**Location 2 - Route Legs with Polyline (line 1046):**
```python
"legs": [
    {
        "pts": route_coords if route_coords else (pickup_coords + dropoff_coords),
        "meta": {"dist": str(distance_meters), "est_dur": str(duration_seconds)},
        "from_seq": 0,
        "to_seq": 1
    }
]
```

**Key Improvements:**
- `"pts"` now contains the full route polyline (list of [lng*1e6, lat*1e6] coordinates)
- Falls back to start/end points if polyline is unavailable
- Distance and duration are actual calculated values
- TaxiCaller dispatcher map shows the exact route path

---

## What Changed

| Aspect | Before | After |
|--------|--------|-------|
| **Distance** | Hardcoded 5000m | Actual from Google Maps |
| **Duration** | Hardcoded 600s | Actual from Google Maps |
| **Route Path (pts)** | Only start/end points | Full polyline with all waypoints |
| **Route Map** | Straight line | Exact route with all turns |
| **Every Booking** | Same values | Unique values per route |
| **Dispatcher View** | Inaccurate | Accurate route visualization |

---

## How It Works

1. **Booking Created** → Customer provides pickup and destination
2. **Route Calculated** → Google Maps Directions API calculates actual route
3. **Data Extracted** →
   - Distance (meters)
   - Duration (seconds)
   - Route polyline (compressed string)
4. **Polyline Decoded** → Compressed polyline converted to [lng*1e6, lat*1e6] coordinate pairs
5. **Sent to TaxiCaller** → Booking includes:
   - Actual distance and duration
   - Full route path with all waypoints
6. **Dispatch Map** → TaxiCaller shows:
   - Accurate distance
   - Correct route with all turns
   - Proper trip visualization for drivers

---

## Requirements

✅ **Google Maps API Key** - Already configured in the app
✅ **Directions API Enabled** - Must be enabled in Google Cloud Console
✅ **Valid Addresses** - Pickup and destination must be valid locations

---

## Testing

To verify the fix is working:

1. Create a booking with specific pickup and destination
2. Check the logs for: `📊 Route data: XXXXm, XXXXs, NNN waypoints`
3. Verify TaxiCaller shows:
   - Correct distance
   - Correct duration
   - Exact route path with all turns
   - Proper visualization on dispatcher map

---

## Fallback Behavior

If Google Maps is unavailable or returns an error:
- Distance: 5000 meters (default)
- Duration: 600 seconds (default)
- Route polyline: Empty list (falls back to start/end points)
- Booking still succeeds with reasonable defaults

---

## Files Modified

- **app.py**
  - Added `decode_polyline()` function (line 812) - Decodes Google Maps polyline format
  - Updated `get_route_distance_and_duration()` function (line 851) - Now returns polyline coordinates
  - Updated function call (line 990) - Captures route_coords
  - Updated route meta in booking payload (line 1023) - Uses actual distance/duration
  - Updated route legs in booking payload (line 1046) - Uses full polyline with fallback

---

## Result

✅ TaxiCaller now receives **accurate route information** for every booking
✅ Dispatch map shows **correct distance and route**
✅ Route polyline includes **all waypoints** for exact path visualization
✅ Drivers see **accurate trip visualization** on their maps
✅ No more hardcoded values
✅ Booking creation still works with fallback defaults
✅ Full route path with all turns and intersections displayed

**Issue Resolved!** 🎉

---

## Technical Details

### Polyline Format
- Google Maps returns compressed polyline strings
- Decoded to [lng*1e6, lat*1e6] coordinate pairs
- Sent to TaxiCaller in the "pts" field under "legs"
- Provides exact route visualization

### Coordinate System
- Longitude and Latitude multiplied by 1,000,000 (1e6)
- Stored as integers for efficiency
- TaxiCaller expects this format for proper map rendering

