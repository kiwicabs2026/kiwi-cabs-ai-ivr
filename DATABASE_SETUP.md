# 🚖 Kiwi Cabs AI IVR - Database Setup

## Quick Start

### 1. Set Database URL
```bash
export DATABASE_URL="postgresql://user:password@host:port/database_name"
```

### 2. Initialize Database
```bash
python init_db.py
```

That's it! ✅

---

## Database Schema

The database has 3 simple tables:

### 1. **customers**
- `id` - Primary key
- `phone_number` - Customer phone (unique)
- `name` - Customer name
- `created_at` - Registration timestamp
- `total_bookings` - Booking count

### 2. **bookings**
- `id` - Primary key
- `customer_phone` - Customer phone number
- `customer_name` - Customer name
- `pickup_location` - Pickup address
- `dropoff_location` - Destination address
- `booking_time` - When booking was created
- `scheduled_time` - When taxi should arrive
- `status` - Booking status (pending/confirmed/cancelled)
- `booking_reference` - Unique booking ID
- `raw_speech` - Original speech input
- `pickup_date` - Date in DD/MM/YYYY format
- `pickup_time` - Time in HH:MM format
- `order_id` - TaxiCaller order ID
- `created_via` - How booking was created (ai_ivr)

### 3. **conversations**
- `id` - Primary key
- `phone_number` - Customer phone
- `message` - Chat message
- `role` - Who sent it (user/assistant)
- `timestamp` - When message was sent

---

## Files

- **db_schema.sql** - Database schema definition
- **init_db.py** - Initialization script
- **DATABASE_SETUP.md** - This file

---

## Troubleshooting

### Connection Error
```bash
# Check DATABASE_URL is set
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Tables Not Created
```bash
# Run initialization again
python init_db.py

# Or manually with psql
psql $DATABASE_URL -f db_schema.sql
```

### Check Tables
```bash
psql $DATABASE_URL -c "\dt"
```

---

## Integration with app.py

The app.py already has `init_db()` function that creates these tables automatically on startup. You can either:

1. **Let app.py create tables** - Just run `python app.py`
2. **Pre-create tables** - Run `python init_db.py` first, then `python app.py`

Both approaches work fine!

---

## Environment Variables

Set this before running:
```bash
export DATABASE_URL="postgresql://username:password@hostname:port/database_name"
```

Example for Render:
```bash
export DATABASE_URL="postgresql://user:pass@dpg-xxx.oregon-postgres.render.com/kiwi_cabs_db"
```

---

**That's all you need!** 🚀

