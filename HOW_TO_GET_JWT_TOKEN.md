# 🔑 How to Get a Fresh JWT Token

## Problem
Your JWT token has expired:
```
"jwt expired"
```

---

## Solution: Generate a New JWT Token

### Method 1: Using cURL (Fastest)

Run this command in your terminal:

```bash
curl "https://api.taxicaller.net/api/v1/jwt/for-key?key=bd624ba9-YOUR-API-KEY&sub=*&ttl=900"
```

**Replace `bd624ba9-YOUR-API-KEY` with your actual TaxiCaller API key**

### Expected Response:
```
eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g
```

---

## Method 2: Using Postman

### Step 1: Create New Request
- Click **+ New** → **Request**
- Name it: `Get JWT Token`

### Step 2: Set URL & Method
- Method: **GET**
- URL: `https://api.taxicaller.net/api/v1/jwt/for-key`

### Step 3: Add Query Parameters
Go to **Params** tab and add:

| Key | Value |
|-----|-------|
| `key` | `bd624ba9-YOUR-API-KEY` |
| `sub` | `*` |
| `ttl` | `900` |

**Replace `bd624ba9-YOUR-API-KEY` with your actual API key**

### Step 4: Send
- Click **Send**
- Copy the response (it's your new JWT token)

---

## Method 3: Using Python

```python
import requests

API_KEY = "bd624ba9-YOUR-API-KEY"  # Replace with your actual key

response = requests.get(
    "https://api.taxicaller.net/api/v1/jwt/for-key",
    params={
        "key": API_KEY,
        "sub": "*",
        "ttl": "900"
    }
)

jwt_token = response.text.strip()
print(f"New JWT Token: {jwt_token}")
```

---

## Method 4: Using Node.js

```javascript
const axios = require('axios');

const API_KEY = "bd624ba9-YOUR-API-KEY";  // Replace with your actual key

axios.get('https://api.taxicaller.net/api/v1/jwt/for-key', {
  params: {
    key: API_KEY,
    sub: '*',
    ttl: '900'
  }
})
.then(response => {
  const jwtToken = response.data;
  console.log(`New JWT Token: ${jwtToken}`);
})
.catch(error => console.error('Error:', error));
```

---

## How to Use the New Token in Postman

### Step 1: Get the Token
Use one of the methods above to get a fresh JWT token

### Step 2: Update POSTMAN_WORKING_MINIMAL.json
Replace the old token in the Authorization header:

**Old:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3MzcxIiwic3ViIjoiKiIsInVpZCI6MCwiZmxhZ3MiOjAsImV4cCI6MTc2MjI5MjU1M30.chuKNi_p-HGPQGccRbQV_YpVinoIPjgGv3L2_O2WB_g
```

**New:**
```
Authorization: Bearer YOUR_NEW_JWT_TOKEN_HERE
```

### Step 3: Send Request
- Go to Postman
- Update the Authorization header with the new token
- Click **Send**

---

## Token Details

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `key` | Your API Key | TaxiCaller API key |
| `sub` | `*` | Subject (wildcard for all) |
| `ttl` | `900` | Time to live in seconds (15 minutes) |

---

## Token Expiration

- **TTL:** 900 seconds = 15 minutes
- **When to refresh:** When you get "jwt expired" error
- **How often:** Generate a new one each time you test

---

## Troubleshooting

### Error: "Invalid API Key"
- Check your API key is correct
- Make sure there are no extra spaces
- Verify the key hasn't been revoked

### Error: "Connection refused"
- Check your internet connection
- Verify TaxiCaller API is online
- Try again in a few seconds

### Error: "401 Unauthorized"
- Your API key is invalid
- Contact TaxiCaller support for a new key

---

## Quick Reference

### cURL Command (Copy & Paste)
```bash
curl "https://api.taxicaller.net/api/v1/jwt/for-key?key=YOUR_API_KEY&sub=*&ttl=900"
```

### Postman URL
```
https://api.taxicaller.net/api/v1/jwt/for-key?key=YOUR_API_KEY&sub=*&ttl=900
```

---

## Status

✅ **READY** - Use one of the methods above to get a fresh JWT token!

