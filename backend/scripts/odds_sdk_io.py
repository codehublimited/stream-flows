import os
import psycopg2
import psycopg2.extras
import logging
import time
from odds_api import OddsAPIClient

# Credentials
API_KEY = "fe244fad09b14ed3c9d7b63af96aa2d7f780720d5407bb87d1e6afc7b55313e6"
PG_PASSWORD = ","

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Connect to Odds-API.io
client = OddsAPIClient(api_key=API_KEY)

# Step 1: Get football events
logger.info("Fetching football events...")
try:
    events = client.get_events(sport="football")
    logger.info(f"Found {len(events)} events.")
except Exception as e:
    logger.error(f"Error fetching events: {e}")
    exit()

# Step 2: For each event, get odds
all_odds = []
for idx, ev in enumerate(events[:20]):  # Limit to 20 for testing
    event_id = ev.get("id")
    if not event_id:
        continue
    try:
        # Get odds with a specific bookmaker (e.g., bet365)
        odds_data = client.get_odds(event_id=event_id, bookmakers="bet365")
        if odds_data:
            all_odds.append((ev, odds_data))
            logger.info(f"Got odds for {ev.get('home_team')} vs {ev.get('away_team')} ({idx+1}/{min(len(events),20)})")
        else:
            logger.warning(f"No odds for {event_id}")
    except Exception as e:
        logger.warning(f"Error for {event_id}: {e}")
    time.sleep(0.5)

logger.info(f"Got odds for {len(all_odds)} events.")

# Step 3: Insert into PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="sports_db",
    user="postgres",
    password=PG_PASSWORD
)
cur = conn.cursor()
inserted = 0

for ev, odds in all_odds:
    home = ev.get("home_team", "Unknown")
    away = ev.get("away_team", "Unknown")
    home_odds = draw_odds = away_odds = None
    if "bookmakers" in odds:
        for bm in odds.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market.get("market") == "1X2":
                    for outcome in market.get("outcomes", []):
                        if outcome.get("name") == home:
                            home_odds = outcome.get("price")
                        elif outcome.get("name") == away:
                            away_odds = outcome.get("price")
                        else:
                            draw_odds = outcome.get("price")
                    break
            if home_odds is not None:
                break

    cur.execute("""
        INSERT INTO odds (bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds, raw_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, ("bet365", home, away, home_odds, draw_odds, away_odds, psycopg2.extras.Json(odds)))
    inserted += 1

conn.commit()
cur.close()
conn.close()
logger.info(f"Inserted {inserted} odds.")
