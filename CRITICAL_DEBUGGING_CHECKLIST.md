# 🚨 Critical Debugging Checklist

## Before We Continue - Answer These Questions

### 1. JWT Token Status
```
❓ Is your JWT token fresh (generated within the last 15 minutes)?
   Answer: YES / NO
   
❓ What is the exact error message you see?
   - "jwt expired"
   - "401 Unauthorized"
   - "500 NullPointerException"
   - Other: ___________
```

### 2. Headers in Postman
```
❓ In Postman, go to Headers tab and verify:
   
   Content-Type: application/json
   ✅ Is this present?
   
   Authorization: Bearer YOUR_TOKEN
   ✅ Is this present?
   ✅ Does it start with "Bearer " (with space)?
   ✅ Is the token fresh (not expired)?
   
   User-Agent: KiwiCabs-AI-IVR/2.1
   ✅ Is this present?
```

### 3. Body in Postman
```
❓ In Postman Body tab:
   ✅ Is "raw" selected?
   ✅ Is "JSON" selected from dropdown?
   ✅ Is the JSON valid (no red squiggly lines)?
   ✅ Did you copy the ENTIRE file content?
```

### 4. URL in Postman
```
❓ Is the URL exactly:
   https://api.taxicaller.net/api/v1/booker/order
   
   ✅ No extra spaces?
   ✅ No typos?
   ✅ Exactly as shown above?
```

### 5. Method in Postman
```
❓ Is the method set to: POST
   ✅ Not GET?
   ✅ Not PUT?
   ✅ POST?
```

---

## What to Check RIGHT NOW

### Check 1: Copy Headers Exactly
In Postman, go to **Headers** tab and add these EXACTLY:

| Key | Value |
|-----|-------|
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g` |
| `User-Agent` | `KiwiCabs-AI-IVR/2.1` |

**⚠️ IMPORTANT:** Replace the Bearer token with a FRESH one from:
```bash
curl "https://api.taxicaller.net/api/v1/jwt/for-key?key=YOUR_API_KEY&sub=*&ttl=900"
```

### Check 2: Copy Body Exactly
In Postman, go to **Body** tab:
1. Select **raw**
2. Select **JSON** from dropdown
3. Delete everything
4. Copy the ENTIRE content from POSTMAN_ULTRA_MINIMAL.json
5. Paste it

### Check 3: Verify URL
In Postman URL bar, make sure it says:
```
https://api.taxicaller.net/api/v1/booker/order
```

### Check 4: Verify Method
In Postman, top left should say: **POST**

---

## If Still Getting 500 Error

The 500 NullPointerException might be coming from TaxiCaller's backend, not your payload.

### Possible Reasons:
1. **API Key is invalid** - Contact TaxiCaller support
2. **Company ID is wrong** - Should be 7371
3. **API endpoint changed** - Check with TaxiCaller
4. **Rate limiting** - Wait a few seconds and try again
5. **TaxiCaller server issue** - Check their status page

---

## Alternative: Test with cURL

Try this command in terminal to test directly:

```bash
curl -X POST https://api.taxicaller.net/api/v1/booker/order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FRESH_JWT_TOKEN" \
  -H "User-Agent: KiwiCabs-AI-IVR/2.1" \
  -d '{
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
            "location": {"name": "Start", "coords": [174813105, -41321728]},
            "times": {"arrive": {"target": 0}},
            "info": {"all": ""},
            "seq": 0
          },
          {
            "actions": [{"@type": "client_action", "item_seq": 0, "action": "out"}],
            "location": {"name": "End", "coords": [174901349, -41210620]},
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
  }'
```

Replace `YOUR_FRESH_JWT_TOKEN` with a token from:
```bash
curl "https://api.taxicaller.net/api/v1/jwt/for-key?key=YOUR_API_KEY&sub=*&ttl=900"
```

---

## Status

⚠️ **NEED MORE INFO** - Answer the questions above to continue debugging!

