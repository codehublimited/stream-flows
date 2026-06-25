import psycopg2

conn = psycopg2.connect(host="localhost", port=5432, dbname="sports_db", user="postgres", password="2026Stream")
cur = conn.cursor()

cur.execute("SELECT * FROM odds LIMIT 5")
columns = [desc[0] for desc in cur.description]
print("Columns:", columns)
print()

rows = cur.fetchall()
for row in rows:
    print(row)

print()
cur.execute("SELECT COUNT(*) FROM odds WHERE home_win_odds IS NOT NULL")
print("Rows with actual odds values (not null):", cur.fetchone()[0])

cur.execute("SELECT DISTINCT bookmaker FROM odds")
print("Bookmakers present:", [r[0] for r in cur.fetchall()])

conn.close()
