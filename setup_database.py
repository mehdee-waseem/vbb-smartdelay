import os
from dotenv import load_dotenv, find_dotenv

# Load secrets from the .env file in the project root (never committed to git)
load_dotenv(find_dotenv(usecwd=True))

import psycopg2
from psycopg2 import sql

# Your Neon connection string
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set. Create a .env file in the project root (see .env.example).")

# Read the SQL schema
with open('init-db.sql', 'r') as f:
    schema_sql = f.read()

# Connect to the database
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("✅ Connected to Neon database!")
    
    # Execute the schema
    cursor.execute(schema_sql)
    conn.commit()
    
    print("✅ Schema created successfully!")
    
    # Verify tables exist
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    
    tables = cursor.fetchall()
    print(f"\n✅ Created {len(tables)} tables:")
    for table in tables:
        print(f"   - {table[0]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")