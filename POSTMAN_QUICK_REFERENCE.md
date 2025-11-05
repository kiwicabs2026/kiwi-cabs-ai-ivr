# 🚀 Postman Quick Reference - TaxiCaller Booking

## 1️⃣ URL
```
POST https://api.taxicaller.net/api/v1/booker/order
```

---

## 2️⃣ Headers
```
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g
User-Agent: KiwiCabs-AI-IVR/2.1
```

---

## 3️⃣ Body (Raw JSON)

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
            "name": "63 Hobart Street, Miramar, Wellington 6003, New Zealand",
            "coords": [174813105, -41321728]
          },
          "times": {
            "arrive": {
              "target": 0
            }
          },
          "info": {
            "all": "Driver instructions here"
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

## ✅ Expected Success Response

```json
{
  "order_id": "12345",
  "status": "confirmed",
  "message": "Booking created successfully"
}
```

**Status Code:** `200` or `201`

---

## ❌ If You Get 500 Error

Check these in the pts array:
- ❌ No empty arrays `[]`
- ❌ No single numbers like `-41212810`
- ✅ All coordinates are `[lng, lat]` pairs
- ✅ All values are integers

---

## 🔧 Customization

### Change Pickup Location
```json
"location": {
  "name": "YOUR ADDRESS HERE",
  "coords": [LNG_TIMES_1E6, LAT_TIMES_1E6]
}
```

### Change Dropoff Location
```json
"location": {
  "name": "YOUR DESTINATION HERE",
  "coords": [LNG_TIMES_1E6, LAT_TIMES_1E6]
}
```

### Change Customer Name
```json
"passenger": {
  "name": "YOUR NAME HERE",
  "email": "customer@kiwicabs.co.nz",
  "phone": "0220881234"
}
```

### Change Distance & Duration
```json
"meta": {
  "est_dur": "1388",
  "dist": "21639"
}
```

---

## 📍 Wellington Coordinates Reference

| Location | Coords |
|----------|--------|
| Miramar (63 Hobart St) | `[174813105, -41321728]` |
| Hutt Central (1/3 Laings Rd) | `[174901349, -41210620]` |
| Newtown (49 Riddiford St) | `[174780939, -41309276]` |

---

## 🎯 Steps to Test

1. Open Postman
2. Create new **POST** request
3. Paste URL: `https://api.taxicaller.net/api/v1/booker/order`
4. Go to **Headers** tab → Add the 3 headers above
5. Go to **Body** tab → Select **raw** → Select **JSON**
6. Paste the JSON payload above
7. Click **Send**
8. Check response status and body

---

## Status

✅ **READY TO TEST** - Copy and paste into Postman!

