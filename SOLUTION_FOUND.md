# 🎉 SOLUTION FOUND! The Root Cause of 500 Error

## The Problem

The TaxiCaller API was returning **500 NullPointerException** when you included the `pts` field in the `legs` array with coordinates.

## The Solution

**Remove the `pts` field from the legs array!** The API doesn't need it for basic bookings.

---

## ✅ Working Payload (Test 4)

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

## ❌ What Was Wrong

```json
"legs": [
  {
    "pts": [
      [174813105, -41321728],
      [174901349, -41210620]
    ],
    "meta": {"dist": "5000", "est_dur": "600"},
    "from_seq": 0,
    "to_seq": 1
  }
]
```

The `pts` field was causing the NullPointerException!

## ✅ What Works

```json
"legs": [
  {
    "meta": {"dist": "5000", "est_dur": "600"},
    "from_seq": 0,
    "to_seq": 1
  }
]
```

Just remove the `pts` field!

---

## Test Results

| Test | Payload | Result |
|------|---------|--------|
| Test 1 | No route | ✅ 200 OK |
| Test 2 | Empty route | ✅ 200 OK |
| Test 3 | Route meta only | ✅ 200 OK |
| Test 4 | Route meta + nodes | ✅ 200 OK |
| Your payload | Route meta + nodes + pts | ❌ 500 Error |

---

## What to Do Now

### Update app.py

In the `send_to_taxicaller()` function, change the legs array from:

```python
"legs": [
    {
        "pts": [pt for pt in (route_coords if route_coords else [pickup_coords, dropoff_coords]) if isinstance(pt, list) and len(pt) == 2 and isinstance(pt[0], int) and isinstance(pt[1], int)],
        "meta": {"dist": str(distance_meters), "est_dur": str(duration_seconds)},
        "from_seq": 0,
        "to_seq": 1
    }
]
```

To:

```python
"legs": [
    {
        "meta": {"dist": str(distance_meters), "est_dur": str(duration_seconds)},
        "from_seq": 0,
        "to_seq": 1
    }
]
```

### Test in Postman

Use this payload:

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

---

## Expected Response

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
    "dispatch_time": 1762294652,
    "job_id": 269151723,
    "vehicle_id": 1746147051
  },
  "order": {
    "order_id": "66943c974e22149f",
    "company_id": 7371,
    ...
  }
}
```

**Status Code:** `200` ✅

---

## Summary

- ❌ **Problem:** `pts` field in legs array was causing NullPointerException
- ✅ **Solution:** Remove the `pts` field from legs array
- ✅ **Result:** API returns 200 OK with booking confirmation

**The fix is simple: just remove the `pts` field!**

