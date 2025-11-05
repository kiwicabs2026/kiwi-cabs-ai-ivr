# ⚡ Get JWT Token - Quick Guide

## 🚀 Fastest Way (30 seconds)

### Option 1: cURL (Recommended)

Open terminal and run:

```bash
curl "https://api.taxicaller.net/api/v1/jwt/for-key?key=bd624ba9-YOUR-API-KEY&sub=*&ttl=900"
```

**Replace `bd624ba9-YOUR-API-KEY` with your actual TaxiCaller API key**

You'll get back a token like:
```
eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g
```

---

### Option 2: Postman

1. Open Postman
2. Create **GET** request to:
   ```
   https://api.taxicaller.net/api/v1/jwt/for-key?key=bd624ba9-YOUR-API-KEY&sub=*&ttl=900
   ```
3. Click **Send**
4. Copy the response

---

### Option 3: Browser

Paste this in your browser address bar:
```
https://api.taxicaller.net/api/v1/jwt/for-key?key=bd624ba9-YOUR-API-KEY&sub=*&ttl=900
```

Replace `bd624ba9-YOUR-API-KEY` with your actual key

---

## 📝 Update Postman Request

### Step 1: Copy Your New Token
From the response above, copy the entire token

### Step 2: Open POSTMAN_WORKING_MINIMAL.json

### Step 3: Find This Line
```
"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g"
```

### Step 4: Replace With Your New Token
```
"Authorization": "Bearer YOUR_NEW_TOKEN_HERE"
```

### Step 5: Send Request
- Go to Postman
- Update the Authorization header
- Click **Send**

---

## ✅ Expected Result

```json
{
  "order_id": "12345",
  "status": "confirmed",
  "message": "Booking created successfully"
}
```

**Status Code:** `200` or `201` ✅

---

## 🔑 Your API Key

Your TaxiCaller API key starts with: `bd624ba9...`

(Full key should be in your environment variables or .env file)

---

## ⏰ Token Validity

- **Expires in:** 15 minutes (900 seconds)
- **When to refresh:** When you get "jwt expired" error
- **How to refresh:** Run the cURL command again

---

## Status

✅ **READY** - Get your token and update Postman!

