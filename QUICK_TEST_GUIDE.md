# ⚡ Quick Test Guide - TaxiCaller Booking API

## 🚀 Test Now in Postman (2 Minutes)

### Step 1: Get Fresh JWT Token
```bash
curl "https://api.taxicaller.net/api/v1/jwt/for-key?key=bd624ba9ead25533de1cdef7fe4e8e61&sub=*&ttl=900"
```

Copy the token from the response.

### Step 2: Open Postman

Create a new POST request with:

**URL:**
```
https://api.taxicaller.net/api/v1/booker/order
```

**Method:** `POST`

### Step 3: Add Headers

| Key | Value |
|-----|-------|
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer YOUR_JWT_TOKEN_HERE` |
| `User-Agent` | `KiwiCabs-AI-IVR/2.1` |

### Step 4: Add Body

Select **raw** and **JSON**, then paste:

```json
{
  "order": {
    "company_id": 7371,
    "provider_id": 0,
    "order_id": 0,
    "items": [
      {
        "@type": "passengers",
        "seq": 0,
        "passenger": {
          "name": "Test Customer",
          "email": "test@test.com",
          "phone": "0220881234"
        },
        "client_id": 0,
        "account": {
          "id": 0,
          "customer_id": 0
        },
        "require": {
          "seats": 1,
          "wc": 0,
          "bags": 1
        },
        "pay_info": [
          {
            "@t": 0,
            "data": ""
          }
        ]
      }
    ],
    "route": {
      "meta": {
        "est_dur": "600",
        "dist": "5000"
      },
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
            "name": "Miramar, Wellington",
            "coords": [174813105, -41321728]
          },
          "times": {
            "arrive": {
              "target": 0
            }
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
            "name": "Newtown, Wellington",
            "coords": [174901349, -41210620]
          },
          "times": {
            "arrive": {
              "target": 0
            }
          },
          "seq": 1
        }
      ],
      "legs": [
        {
          "meta": {
            "dist": "5000",
            "est_dur": "600"
          },
          "from_seq": 0,
          "to_seq": 1
        }
      ]
    }
  }
}
```

### Step 5: Click Send

### Expected Result:

**Status:** `200 OK` ✅

**Response:**
```json
{
  "dispatch_options": {
    "auto_assign": true,
    "dispatch_time": "2025-11-04T22:17:32.263Z",
    "vehicle_id": 1746147051
  },
  "order_token": "eyJhbGciOiJIUzI1NiJ9...",
  "meta": {
    "driver_id": 68827,
    "job_id": 269151723,
    "vehicle_id": 1746147051
  },
  "order": {
    "order_id": "66943c974e22149f",
    "company_id": 7371
  }
}
```

---

## ✅ Verification Checklist

Before clicking Send:

- [ ] URL is correct: `https://api.taxicaller.net/api/v1/booker/order`
- [ ] Method is: `POST`
- [ ] Headers tab has 3 headers
- [ ] Authorization header has fresh JWT token
- [ ] Body is raw JSON
- [ ] JSON is valid (no red squiggly lines)

---

## ❌ If You Get an Error

### Error: "jwt expired"
- Generate a new JWT token (Step 1)
- Update Authorization header

### Error: "401 Unauthorized"
- Check Authorization header is present
- Check Bearer token is correct
- Generate a new token

### Error: "500 NullPointerException"
- Check JSON is valid
- Check all required fields are present
- Check coordinates are integers (not floats)

---

## 🎯 Key Points

✅ **NO `pts` field in legs array** - This was causing the 500 error!
✅ **Legs array must have:** `meta`, `from_seq`, `to_seq`
✅ **Nodes array must have:** `actions`, `location`, `times`, `seq`
✅ **Coordinates must be:** integers like `[174813105, -41321728]`

---

## 📋 Files

- `POSTMAN_WORKING_FIXED.json` - Ready-to-use payload
- `FIX_SUMMARY.md` - Detailed explanation
- `SOLUTION_FOUND.md` - Technical analysis

---

## 🚀 Ready to Test!

Follow the 5 steps above and you should get a 200 OK response! 🎉

