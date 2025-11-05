# 📮 Postman Testing Guide - TaxiCaller Booking API

## Overview

This guide provides everything you need to test the TaxiCaller booking API directly in Postman, without going through the IVR system.

---

## 📋 Files Provided

1. **POSTMAN_QUICK_REFERENCE.md** - Quick copy-paste guide
2. **POSTMAN_EXACT_PAYLOAD.json** - Full payload from your console output
3. **POSTMAN_BOOKING_TEST.md** - Detailed setup instructions
4. **This file** - Complete testing guide

---

## 🚀 Quick Start (2 Minutes)

### Step 1: Open Postman
- Launch Postman application
- Click **+ New** → **Request**

### Step 2: Set URL & Method
- Method: **POST**
- URL: `https://api.taxicaller.net/api/v1/booker/order`

### Step 3: Add Headers
Go to **Headers** tab and add:

| Key | Value |
|-----|-------|
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhY3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g` |
| `User-Agent` | `KiwiCabs-AI-IVR/2.1` |

### Step 4: Add Body
- Go to **Body** tab
- Select **raw**
- Select **JSON** from dropdown
- Copy the entire content from **POSTMAN_EXACT_PAYLOAD.json**
- Paste it into the body

### Step 5: Send
- Click **Send**
- Check the response

---

## ✅ Expected Success Response

**Status Code:** `200` or `201`

```json
{
  "order_id": "12345",
  "status": "confirmed",
  "message": "Booking created successfully"
}
```

---

## ❌ Troubleshooting

### Error: 401 Unauthorized
**Problem:** Bearer token is invalid or expired

**Solution:**
1. Generate a new JWT token from your API key
2. Replace the Bearer token in the Authorization header

### Error: 500 NullPointerException
**Problem:** Malformed data in the payload

**Check:**
- ✅ All coordinates are integers (not floats)
- ✅ All pts are `[lng, lat]` pairs
- ✅ No empty arrays `[]` in pts
- ✅ No single numbers in pts
- ✅ All required fields are present

**Solution:**
1. Validate JSON syntax (use JSON validator)
2. Check pts array for malformed data
3. Ensure all coordinates are `[int, int]` format

### Error: 400 Bad Request
**Problem:** Invalid JSON or missing required fields

**Solution:**
1. Validate JSON syntax
2. Check all required fields are present
3. Verify field names match exactly (case-sensitive)

---

## 🔧 Customization Examples

### Example 1: Different Pickup Location

Find this section:
```json
"location": {
  "name": "63 Hobart Street, Miramar, Wellington 6003, New Zealand",
  "coords": [174813105, -41321728]
}
```

Change to:
```json
"location": {
  "name": "Your Address Here",
  "coords": [YOUR_LNG_TIMES_1E6, YOUR_LAT_TIMES_1E6]
}
```

### Example 2: Different Customer Name

Find this section:
```json
"passenger": {
  "name": "Sell Abraham",
  "email": "customer@kiwicabs.co.nz",
  "phone": "0220881234"
}
```

Change to:
```json
"passenger": {
  "name": "Your Name",
  "email": "customer@kiwicabs.co.nz",
  "phone": "0220881234"
}
```

### Example 3: Different Distance & Duration

Find this section:
```json
"meta": {
  "est_dur": "1388",
  "dist": "21639"
}
```

Change to:
```json
"meta": {
  "est_dur": "600",
  "dist": "5000"
}
```

---

## 📍 Wellington Coordinates Reference

Use these coordinates for testing:

| Location | Coordinates | Notes |
|----------|-------------|-------|
| Miramar (63 Hobart St) | `[174813105, -41321728]` | Pickup point |
| Hutt Central (1/3 Laings Rd) | `[174901349, -41210620]` | Dropoff point |
| Newtown (49 Riddiford St) | `[174780939, -41309276]` | Alternative |
| CBD (Lambton Quay) | `[174876000, -41286000]` | Alternative |

**Format:** `[longitude * 1000000, latitude * 1000000]`

---

## 🧪 Test Scenarios

### Test 1: Minimal Booking (No Polyline)
Use just 2 points in pts array:
```json
"pts": [
  [174813105, -41321728],
  [174901349, -41210620]
]
```

### Test 2: Full Booking (With Polyline)
Use the full payload from POSTMAN_EXACT_PAYLOAD.json (376 waypoints)

### Test 3: Different Customer
Change the passenger name and phone number

### Test 4: Different Route
Change pickup and dropoff coordinates and addresses

---

## 📊 Response Analysis

### Success Response
```json
{
  "order_id": "12345",
  "status": "confirmed",
  "message": "Booking created successfully"
}
```
- ✅ Status code: 200 or 201
- ✅ Contains order_id
- ✅ Status is "confirmed"

### Error Response
```json
{
  "errors": [
    {
      "code": 0,
      "flags": 128,
      "err_msg": "java.lang.NullPointerException",
      "status": 500
    }
  ]
}
```
- ❌ Status code: 500
- ❌ Contains error message
- ❌ Check payload for malformed data

---

## 🔍 Validation Checklist

Before sending, verify:

- [ ] URL is correct: `https://api.taxicaller.net/api/v1/booker/order`
- [ ] Method is POST
- [ ] Content-Type header is `application/json`
- [ ] Authorization header has Bearer token
- [ ] JSON is valid (no syntax errors)
- [ ] All coordinates are integers
- [ ] All pts are `[lng, lat]` pairs
- [ ] No empty arrays in pts
- [ ] No single numbers in pts
- [ ] All required fields are present
- [ ] Passenger name is not empty
- [ ] Phone number is valid format

---

## 💡 Tips

1. **Save the request** - Click Save to reuse later
2. **Use environment variables** - Store API key in Postman environment
3. **Test incrementally** - Start with minimal payload, add complexity
4. **Check response time** - Should be < 5 seconds
5. **Monitor TaxiCaller** - Check dispatcher map after successful booking

---

## 📞 Support

If you get errors:
1. Check the troubleshooting section above
2. Verify all coordinates are integers
3. Validate JSON syntax
4. Check Bearer token is valid
5. Review the payload structure

---

## Status

✅ **READY FOR TESTING** - All files provided, follow the quick start guide!

