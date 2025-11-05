# 📮 Postman Booking Test Data

## TaxiCaller API Booking Endpoint

**URL:** `https://api.taxicaller.net/api/v1/booker/order`

**Method:** `POST`

---

## Headers

```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g",
  "User-Agent": "KiwiCabs-AI-IVR/2.1"
}
```

---

## Request Body (Raw JSON)

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
          "name": "Sell Abraham",
          "email": "customer@kiwicabs.co.nz",
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
        "est_dur": "1388",
        "dist": "21639"
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
            "name": "63 Hobart Street, Miramar, Wellington 6003, New Zealand",
            "coords": [
              174813105,
              -41321728
            ]
          },
          "times": {
            "arrive": {
              "target": 0
            }
          },
          "info": {
            "all": "ExxonMobil"
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
            "name": "1/3 Laings Road, Hutt Central, Lower Hutt 5010, New Zealand",
            "coords": [
              174901349,
              -41210620
            ]
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
            [174813170, -41321550],
            [174810960, -41321060],
            [174809940, -41320810],
            [174809220, -41320670],
            [174809280, -41320340],
            [174809290, -41319530],
            [174809320, -41318900],
            [174809490, -41317570],
            [174809470, -41317470],
            [174809440, -41317380],
            [174809380, -41317300],
            [174809240, -41317180],
            [174809050, -41317190],
            [174808830, -41317120],
            [174808350, -41316900],
            [174808200, -41316860],
            [174808020, -41316830],
            [174807740, -41316840],
            [174806220, -41317110],
            [174805010, -41317300]
          ],
          "meta": {
            "dist": "21639",
            "est_dur": "1388"
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

## Postman Setup Steps

### 1. Create New Request
- Click **+ New**
- Select **Request**
- Name it: `TaxiCaller Booking Test`

### 2. Set Method & URL
- Method: **POST**
- URL: `https://api.taxicaller.net/api/v1/booker/order`

### 3. Add Headers
- Go to **Headers** tab
- Add:
  - Key: `Content-Type` | Value: `application/json`
  - Key: `Authorization` | Value: `Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g`
  - Key: `User-Agent` | Value: `KiwiCabs-AI-IVR/2.1`

### 4. Add Body
- Go to **Body** tab
- Select **raw**
- Select **JSON** from dropdown
- Paste the JSON payload above

### 5. Send Request
- Click **Send**
- Check response status (should be 200 or 201)

---

## Expected Response (Success)

```json
{
  "order_id": "12345",
  "status": "confirmed",
  "message": "Booking created successfully"
}
```

---

## Expected Response (Error - Still Getting 500)

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

If you still get 500, check:
1. ✅ All coordinates are integers (not floats)
2. ✅ All pts are `[lng, lat]` pairs
3. ✅ No empty arrays `[]` in pts
4. ✅ No single numbers in pts
5. ✅ Bearer token is valid and not expired

---

## Test Variations

### Test 1: Minimal Booking (Just Start & End)
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
          "name": "Test User",
          "email": "test@kiwicabs.co.nz",
          "phone": "0220881234"
        },
        "client_id": 0,
        "account": {"id": 0, "customer_id": 0},
        "require": {"seats": 1, "wc": 0, "bags": 1},
        "pay_info": [{"@t": 0, "data": ""}]
      }
    ],
    "route": {
      "meta": {"est_dur": "600", "dist": "5000"},
      "nodes": [
        {
          "actions": [{"@type": "client_action", "item_seq": 0, "action": "in"}],
          "location": {
            "name": "63 Hobart Street, Miramar, Wellington 6003, New Zealand",
            "coords": [174813105, -41321728]
          },
          "times": {"arrive": {"target": 0}},
          "info": {"all": ""},
          "seq": 0
        },
        {
          "actions": [{"@type": "client_action", "item_seq": 0, "action": "out"}],
          "location": {
            "name": "1/3 Laings Road, Hutt Central, Lower Hutt 5010, New Zealand",
            "coords": [174901349, -41210620]
          },
          "times": {"arrive": {"target": 0}},
          "info": {"all": ""},
          "seq": 1
        }
      ],
      "legs": [
        {
          "pts": [[174813105, -41321728], [174901349, -41210620]],
          "meta": {"dist": "5000", "est_dur": "600"},
          "from_seq": 0,
          "to_seq": 1
        }
      ]
    }
  }
}
```

---

## Debugging Tips

### If you get 401 Unauthorized
- Bearer token is invalid or expired
- Generate a new JWT token from your API key

### If you get 500 NullPointerException
- Check pts field for malformed data
- Ensure all coordinates are `[int, int]` format
- Verify no empty arrays or single numbers in pts

### If you get 400 Bad Request
- Check JSON syntax
- Verify all required fields are present
- Check coordinate format (should be integers, not floats)

---

## cURL Command (Alternative)

```bash
curl -X POST https://api.taxicaller.net/api/v1/booker/order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g" \
  -H "User-Agent: KiwiCabs-AI-IVR/2.1" \
  -d '{
    "order": {
      "company_id": 7371,
      "provider_id": 0,
      "order_id": 0,
      "items": [...]
    }
  }'
```

---

## Status

✅ **READY FOR TESTING** - Use this payload in Postman to test the booking endpoint

