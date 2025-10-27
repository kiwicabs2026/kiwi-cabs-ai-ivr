# 🚖 Kiwi Cabs AI IVR - Setup Instructions

## What You Have

✅ **3 Database Files:**
1. `db_schema.sql` - Database schema (3 tables: customers, bookings, conversations)
2. `init_db.py` - Simple initialization script
3. `DATABASE_SETUP.md` - Detailed setup guide

✅ **Minimal & Clean:**
- Only tables needed for app.py
- No unnecessary fields or tables
- Ready to run immediately

---

## How to Use

### Option 1: Let app.py Create Tables (Easiest)
```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
python app.py
```
The app will automatically create tables on startup.

### Option 2: Pre-Create Tables
```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
python init_db.py
python app.py
```

### Option 3: Manual with psql
```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
psql $DATABASE_URL -f db_schema.sql
python app.py
```

---

## Database Tables

### customers
- Stores customer info
- Fields: id, phone_number, name, created_at, total_bookings

### bookings
- Stores booking details
- Fields: id, customer_phone, customer_name, pickup_location, dropoff_location, booking_time, scheduled_time, status, booking_reference, raw_speech, pickup_date, pickup_time, order_id, created_via

### conversations
- Stores chat history
- Fields: id, phone_number, message, role, timestamp

---

## That's It!

No extra documentation, no unnecessary tables, just what app.py needs to run.

**Ready to deploy!** 🚀

