import psycopg2
import os

PG_PASSWORD = os.environ.get('PG_PASSWORD', 'your_password')
conn = psycopg2.connect(host='localhost', port=5432, dbname='sports_db', user='postgres', password=PG_PASSWORD)
cur = conn.cursor()

# Check bond 1 data
cur.execute('SELECT id, match_ids, predictions FROM bonds WHERE id=1')
row = cur.fetchone()
if row:
    print(f'Bond 1: match_ids={row[1]}, predictions={row[2]}, type match_ids={type(row[1])}, predictions type={type(row[2])}')
else:
    print('Bond 1 not found')

# Check teams table columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='teams'")
cols = cur.fetchall()
print('Teams columns:', [c[0] for c in cols])

# Check a sample match with its team IDs
cur.execute("SELECT match_id, home_team_id, away_team_id FROM matches LIMIT 3")
matches = cur.fetchall()
print('Sample matches (match_id, home_team_id, away_team_id):', matches)

cur.close()
conn.close()
