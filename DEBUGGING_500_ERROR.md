# 🔍 Debugging 500 NullPointerException Error

## Problem
You're still getting 500 NullPointerException even with the working payload.

---

## Possible Causes

### 1. ❌ JWT Token Expired
**Error:** `"jwt expired"`

**Solution:**
- Generate a new JWT token
- See: `GET_JWT_QUICK.md`

### 2. ❌ Invalid Coordinates Format
**Problem:** Coordinates must be integers, not floats

**Check:**
```json
"coords": [174813105, -41321728]  // ✅ Integers
"coords": [174.813105, -41.321728]  // ❌ Floats - WRONG!
```

### 3. ❌ Missing Required Fields
**Problem:** TaxiCaller requires ALL these fields:

```json
{
  "order": {
    "company_id": 7371,        // ✅ Required
    "provider_id": 0,          // ✅ Required
    "order_id": 0,             // ✅ Required
    "items": [
      {
        "@type": "passengers", // ✅ Required
        "seq": 0,              // ✅ Required
        "passenger": {
          "name": "...",       // ✅ Required
          "email": "...",      // ✅ Required
          "phone": "..."       // ✅ Required
        },
        "client_id": 0,        // ✅ Required
        "account": {
          "id": 0,             // ✅ Required
          "customer_id": 0     // ✅ Required
        },
        "require": {
          "seats": 1,          // ✅ Required
          "wc": 0,             // ✅ Required
          "bags": 1            // ✅ Required
        },
        "pay_info": [
          {
            "@t": 0,           // ✅ Required
            "data": ""         // ✅ Required (empty string, not null)
          }
        ]
      }
    ],
    "route": {
      "meta": {
        "est_dur": "600",      // ✅ Required (string)
        "dist": "5000"         // ✅ Required (string)
      },
      "nodes": [
        {
          "actions": [...],    // ✅ Required
          "location": {...},   // ✅ Required
          "times": {...},      // ✅ Required
          "info": {...},       // ✅ Required
          "seq": 0             // ✅ Required
        },
        {
          "actions": [...],    // ✅ Required
          "location": {...},   // ✅ Required
          "times": {...},      // ✅ Required
          "info": {...},       // ✅ Required
          "seq": 1             // ✅ Required
        }
      ],
      "legs": [
        {
          "pts": [...],        // ✅ Required (array of [lng, lat])
          "meta": {...},       // ✅ Required
          "from_seq": 0,       // ✅ Required
          "to_seq": 1          // ✅ Required
        }
      ]
    }
  }
}
```

### 4. ❌ Invalid PTS Array
**Problem:** pts must be array of `[lng, lat]` pairs

**Check:**
```json
"pts": [
  [174813105, -41321728],    // ✅ Valid
  [174901349, -41210620]     // ✅ Valid
]

// ❌ INVALID:
"pts": [
  [174813105, -41321728],
  [],                        // ❌ Empty array
  -41210620                  // ❌ Single number
]
```

### 5. ❌ String vs Number Mismatch
**Problem:** Some fields must be strings, others must be numbers

**Check:**
```json
"est_dur": "600",            // ✅ String
"dist": "5000",              // ✅ String
"coords": [174813105, -41321728],  // ✅ Numbers
"target": 0                  // ✅ Number
```

### 6. ❌ Null Values
**Problem:** TaxiCaller doesn't accept null values

**Check:**
```json
"data": ""                   // ✅ Empty string
"data": null                 // ❌ Null - WRONG!
"all": ""                    // ✅ Empty string
"all": null                  // ❌ Null - WRONG!
```

---

## Step-by-Step Debugging

### Step 1: Test Ultra Minimal Payload
Use: **POSTMAN_ULTRA_MINIMAL.json**

This has:
- ✅ Only 2 waypoints (simplest possible)
- ✅ All required fields
- ✅ No complex data

If this works → Your issue is with the polyline data
If this fails → Your issue is with the payload structure

### Step 2: Validate JSON Syntax
Use an online JSON validator:
- https://jsonlint.com/
- https://www.jsonschemavalidator.net/

Paste your payload and check for syntax errors

### Step 3: Check Coordinates
Print each coordinate and verify:
- ✅ All are integers (not floats)
- ✅ All are in range: `[lng*1e6, lat*1e6]`
- ✅ No `[0, 0]` values
- ✅ No empty arrays `[]`

### Step 4: Check Required Fields
Verify ALL these fields exist:
- ✅ `order.company_id`
- ✅ `order.provider_id`
- ✅ `order.order_id`
- ✅ `items[0].@type`
- ✅ `items[0].passenger.name`
- ✅ `items[0].passenger.email`
- ✅ `items[0].passenger.phone`
- ✅ `items[0].account.id`
- ✅ `items[0].account.customer_id`
- ✅ `route.meta.est_dur`
- ✅ `route.meta.dist`
- ✅ `route.nodes[0]` and `route.nodes[1]`
- ✅ `route.legs[0].pts`
- ✅ `route.legs[0].meta`

### Step 5: Check Data Types
Verify:
- ✅ `est_dur` is STRING: `"600"` not `600`
- ✅ `dist` is STRING: `"5000"` not `5000`
- ✅ `coords` are NUMBERS: `[174813105, -41321728]` not `["174813105", "-41321728"]`
- ✅ `target` is NUMBER: `0` not `"0"`

---

## Testing Payloads (In Order)

### Test 1: Ultra Minimal (2 waypoints)
**File:** `POSTMAN_ULTRA_MINIMAL.json`
- Simplest possible payload
- If this fails → Payload structure issue
- If this works → Polyline issue

### Test 2: Working Minimal (120+ waypoints)
**File:** `POSTMAN_WORKING_MINIMAL.json`
- Full polyline from Google Maps
- If this fails → Polyline data issue
- If this works → Your setup is correct

### Test 3: Exact Payload (376 waypoints)
**File:** `POSTMAN_EXACT_PAYLOAD.json`
- Full payload from your console output
- Should definitely work

---

## Common Mistakes

| Mistake | Wrong | Right |
|---------|-------|-------|
| Coordinates as floats | `[174.813, -41.321]` | `[174813000, -41321000]` |
| Distance/duration as numbers | `"dist": 5000` | `"dist": "5000"` |
| Null values | `"data": null` | `"data": ""` |
| Empty arrays in pts | `[[...], [], [...]]` | `[[...], [...]]` |
| Missing fields | Omit optional fields | Include ALL fields |
| String coordinates | `"coords": "[174813, -41321]"` | `"coords": [174813, -41321]` |

---

## If Still Getting 500

1. **Check JWT token** - Is it expired?
2. **Validate JSON** - Use jsonlint.com
3. **Test ultra minimal** - Use POSTMAN_ULTRA_MINIMAL.json
4. **Check coordinates** - Are they integers?
5. **Check required fields** - Are ALL fields present?
6. **Check data types** - Are strings/numbers correct?
7. **Check for null values** - Use empty strings instead

---

## Status

✅ **READY** - Follow the debugging steps above!

