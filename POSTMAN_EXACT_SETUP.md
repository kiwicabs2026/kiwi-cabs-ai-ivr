# 📮 Postman Exact Setup - Step by Step

## ⚠️ CRITICAL: Follow These Steps EXACTLY

---

## Step 1: Generate Fresh JWT Token

### In Terminal/PowerShell:
```bash
curl "https://api.taxicaller.net/api/v1/jwt/for-key?key=bd624ba9-YOUR-API-KEY&sub=*&ttl=900"
```

**Replace `bd624ba9-YOUR-API-KEY` with your actual TaxiCaller API key**

You'll get a response like:
```
eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g
```

**Copy this entire token** - you'll need it in Step 3.

---

## Step 2: Open Postman

1. Launch Postman
2. Click **+ New**
3. Select **Request**
4. Name it: `TaxiCaller Test`
5. Click **Create**

---

## Step 3: Set URL & Method

### In the URL bar at the top:
```
https://api.taxicaller.net/api/v1/booker/order
```

### In the Method dropdown (left of URL):
```
POST
```

---

## Step 4: Add Headers

### Click the **Headers** tab

Add these headers **EXACTLY** (case-sensitive):

| Key | Value |
|-----|-------|
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer YOUR_JWT_TOKEN_HERE` |
| `User-Agent` | `KiwiCabs-AI-IVR/2.1` |

**⚠️ IMPORTANT:** Replace `YOUR_JWT_TOKEN_HERE` with the token from Step 1

**Example:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g
```

---

## Step 5: Add Body

### Click the **Body** tab

### Select **raw** (radio button)

### Select **JSON** from the dropdown (right side)

### Delete any existing content

### Copy the ENTIRE content below and paste it:

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
          "name": "Test",
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
            "name": "Start",
            "coords": [174813105, -41321728]
          },
          "times": {
            "arrive": {
              "target": 0
            }
          },
          "info": {
            "all": ""
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
            "name": "End",
            "coords": [174901349, -41210620]
          },
          "times": {
            "arrive": {
              "target": 0
            }
          },
          "info": {
            "all": ""
          },
          "seq": 1
        }
      ],
      "legs": [
        {
          "pts": [
            [174813105, -41321728],
            [174901349, -41210620]
          ],
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

---

## Step 6: Send Request

### Click the **Send** button (blue button on the right)

---

## Step 7: Check Response

### Look at the response section below

**Expected Success Response:**
```json
{
  "order_id": "12345",
  "status": "confirmed",
  "message": "Booking created successfully"
}
```

**Status Code:** `200` or `201` ✅

---

## If You Get 500 Error

### Check These:

1. **Is Authorization header present?**
   - Go to Headers tab
   - Look for `Authorization` row
   - Should have value: `Bearer YOUR_TOKEN`

2. **Is the Bearer token fresh?**
   - Generate a new one from Step 1
   - Replace in Authorization header

3. **Is the URL correct?**
   - Should be: `https://api.taxicaller.net/api/v1/booker/order`
   - No extra spaces or typos

4. **Is the method POST?**
   - Top left should say: `POST`

5. **Is the body raw JSON?**
   - Body tab should show: **raw** selected
   - Dropdown should show: **JSON** selected

6. **Is the JSON valid?**
   - No red squiggly lines in the body
   - Use jsonlint.com to validate

---

## Troubleshooting

### Error: "jwt expired"
- Generate a new JWT token (Step 1)
- Update Authorization header

### Error: "401 Unauthorized"
- Check Authorization header is present
- Check Bearer token is correct
- Generate a new token

### Error: "500 NullPointerException"
- Check all headers are present
- Check Authorization header has "Bearer " prefix
- Check JSON body is valid
- Check all coordinates are integers

### Error: "Connection refused"
- Check internet connection
- Check URL is correct
- Wait a few seconds and try again

---

## Verification Checklist

Before clicking Send, verify:

- [ ] URL: `https://api.taxicaller.net/api/v1/booker/order`
- [ ] Method: `POST`
- [ ] Headers tab has 3 headers:
  - [ ] `Content-Type: application/json`
  - [ ] `Authorization: Bearer YOUR_TOKEN`
  - [ ] `User-Agent: KiwiCabs-AI-IVR/2.1`
- [ ] Body tab:
  - [ ] **raw** is selected
  - [ ] **JSON** is selected
  - [ ] JSON is pasted and valid
- [ ] JWT token is fresh (< 15 minutes old)

---

## Status

✅ **READY** - Follow these steps exactly!

