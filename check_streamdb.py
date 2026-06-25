import os
import psycopg2

url = os.environ["DATABASE_URL"]
conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute("SELECT version()")
print("Connected successfully!")
print(cur.fetchone()[0])
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=" + chr(39) + "public" + chr(39))
tables = [r[0] for r in cur.fetchall()]
print("Tables found:", tables)
conn.close()
