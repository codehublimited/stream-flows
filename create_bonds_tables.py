import psycopg2
import json
import os

PG_PASSWORD = os.environ.get('PG_PASSWORD', '')
if not PG_PASSWORD:
    print("PG_PASSWORD environment variable not set.")
    exit(1)

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="sports_db",
    user="postgres",
    password=PG_PASSWORD
)
cur = conn.cursor()

# 1. Create bonds table
cur.execute("""
    CREATE TABLE IF NOT EXISTS bonds (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        bond_type VARCHAR(20) NOT NULL,
        match_ids INTEGER[] NOT NULL,
        predictions JSONB NOT NULL,
        price INTEGER NOT NULL,
        expires_at TIMESTAMP,
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT NOW()
    )
""")

# 2. Create user_bond_unlocks table
cur.execute("""
    CREATE TABLE IF NOT EXISTS user_bond_unlocks (
        user_id INTEGER NOT NULL,
        bond_id INTEGER NOT NULL,
        unlocked_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (user_id, bond_id)
    )
""")

# 3. Insert a sample bond (Judas Mix)
# Replace these match IDs with real ones from your matches table
sample_match_ids = [12345, 12346, 12347, 12348, 12349, 12350]
sample_predictions = {
    str(12345): {"result": "home"},
    str(12346): {"result": "draw"},
    str(12347): {"result": "away"},
    str(12348): {"result": "home"},
    str(12349): {"result": "home"},
    str(12350): {"result": "draw"}
}
cur.execute("""
    INSERT INTO bonds (title, description, bond_type, match_ids, predictions, price, expires_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
""", (
    "Judas Mix – UCL",
    "Predict the correct result for 6 Champions League matches.",
    "judas_mix",
    sample_match_ids,
    json.dumps(sample_predictions),
    50,
    "2026-07-01 00:00:00"
))

conn.commit()
cur.close()
conn.close()
print("Bonds tables created and sample bond inserted.")
