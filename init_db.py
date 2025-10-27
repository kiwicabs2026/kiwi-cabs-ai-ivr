#!/usr/bin/env python3
"""
Simple database initialization script for Kiwi Cabs AI IVR
Reads db_schema.sql and creates tables
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Get PostgreSQL connection from DATABASE_URL"""
    DATABASE_URL = "postgresql://kiwi_cabs_ai_ivr_db_q3t8_user:sG65N2kzbFBPWJTyAwNpVVwwHfOq81ZE@dpg-d3ta606mcj7s73a8j2h0-a.oregon-postgres.render.com/kiwi_cabs_ai_ivr_db_q3t8"
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        return None
    
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        print("✅ Database connection successful")
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def init_database():
    """Initialize database with schema"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        print("\n📊 Creating database tables...")
        
        # Read schema file
        with open('db_schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # Execute schema
        cur.execute(schema_sql)
        conn.commit()
        
        print("✅ Database tables created successfully")
        
        # Verify tables
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        tables = cur.fetchall()
        print(f"\n✅ Found {len(tables)} tables:")
        for table in tables:
            print(f"   • {table['table_name']}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.close()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚖 Kiwi Cabs AI IVR - Database Initialization")
    print("="*60)
    
    success = init_database()
    
    if success:
        print("\n✅ Database initialization completed!")
        print("🚀 Ready to start the application")
    else:
        print("\n❌ Database initialization failed!")
    
    exit(0 if success else 1)

