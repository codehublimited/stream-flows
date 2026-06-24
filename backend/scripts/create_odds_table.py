import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="sports_db",
    user="postgres",
    password=","
)
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS odds (
        id SERIAL PRIMARY KEY,
        match_id TEXT,
        bookmaker VARCHAR(50) NOT NULL,
        home_team VARCHAR(100) NOT NULL,
        away_team VARCHAR(100) NOT NULL,
        home_win_odds FLOAT        draw_odds FLOAT,
        away_win_odds FLOAT,
        over_odds FLOAT,
        under_odds FLOAT,
        raw_data JSONB,
        fetched_at TIMESTAMP DEFAULT NOW()
    );
""")
conn.commit()
cur.close()
conn.close()
print("Odds table created (or already exists).")
