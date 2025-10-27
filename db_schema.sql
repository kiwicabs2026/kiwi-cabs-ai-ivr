-- Kiwi Cabs AI IVR - Minimal Database Schema
-- Only includes tables needed for app.py

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_bookings INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone_number);

CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    customer_phone VARCHAR(20) NOT NULL,
    customer_name VARCHAR(100),
    pickup_location TEXT NOT NULL,
    dropoff_location TEXT,
    booking_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    booking_reference VARCHAR(100),
    raw_speech TEXT,
    pickup_date VARCHAR(20),
    order_id VARCHAR(20),
    pickup_time VARCHAR(20),
    created_via VARCHAR(20) DEFAULT 'ai_ivr'
);

CREATE INDEX IF NOT EXISTS idx_bookings_phone ON bookings(customer_phone);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_booking_time ON bookings(booking_time);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    message TEXT,
    role VARCHAR(10),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_phone ON conversations(phone_number);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);

