import psycopg2

try:
    conn = psycopg2.connect(host="localhost", port=5432, dbname="sports_db", user="postgres", password="2026Stream")
    cur = conn.cursor()
    cur.execute("SELECT to_regclass(\'public.odds\')")
    exists = cur.fetchone()[0]
    print("odds table in sports_db exists:", exists is not None)
    if exists:
        cur.execute("SELECT COUNT(*) FROM odds")
        print("Row count:", cur.fetchone()[0])
    conn.close()
except Exception as e:
    print("Could not connect to sports_db:", e)
