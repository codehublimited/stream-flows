import requests
import psycopg2
import psycopg2.extras
import logging
import time
import json

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

API_KEY = "fe244fad09b14ed3c9d7b63af96aa2d7f780720d5407bb87d1e6afc7b55313e6"
PG_PASSWORD = "your_postgres_password"  # 2026Stream

# ------------------------------------------------------------
# Step 1: Get bookmakers
# ------------------------------------------------------------
logger.info("Fetching bookmakers...")
bm_url = f"https://api.odds-api.io/v3/bookmakers?apiKey={API_KEY}"
r = requests.get(bm_url, timeout=10)
if r.status_code != 200:
    logger.error(f"Failed: {r.status_code} - {r.text[:200]}")
    exit()
bookmakers = r.json()
logger.info(f"Found {len(bookmakers)} bookmakers.")

# Find Bet365
chosen = None
for bm in bookmakers:
    name = bm.get("name", "")
    if name == "Bet365":
        chosen = name
        break
if not chosen:
    for bm in bookmakers:
        if "bet365" in bm.get("name", "").lower():
            chosen = bm.get("name")
            break
if not chosen:
    chosen = bookmakers[0].get("name") if bookmakers else None
if not chosen:
    logger.error("No bookmaker found.")
    exit()
logger.info(f"Using bookmaker: {chosen}")

# ------------------------------------------------------------
# Step 2: Get events
# ------------------------------------------------------------
logger.info("Fetching events...")
events_url = f"https://api.odds-api.io/v3/events?sport=football&apiKey={API_KEY}"
r = requests.get(events_url, timeout=30)
if r.status_code != 200:
    logger.error(f"Failed: {r.status_code} - {r.text[:200]}")
    exit()
events = r.json()
logger.info(f"Found {len(events)} events.")

# Sample first event to understand structure
if events and isinstance(events, list) and len(events) > 0:
    ev0 = events[0]
    logger.info(f"Sample event keys: {list(ev0.keys())}")
    # Try to get home and away names
    home_candidate = ev0.get("home_team")
    away_candidate = ev0.get("away_team")
    logger.info(f"Home team type: {type(home_candidate)}, value: {home_candidate}")
    logger.info(f"Away team type: {type(away_candidate)}, value: {away_candidate}")

# ------------------------------------------------------------
# Step 3: Get odds for up to 5 events
# ------------------------------------------------------------
all_odds = []
limit = min(5, len(events))
for idx, ev in enumerate(events[:limit]):
    event_id = ev.get("id")
    if not event_id:
        continue

    # Extract team names
    home = ev.get("home_team")
    away = ev.get("away_team")
    if isinstance(home, dict):
        home = home.get("name", "Unknown")
    elif home is None:
        home = "Unknown"
    if isinstance(away, dict):
        away = away.get("name", "Unknown")
    elif away is None:
        away = "Unknown"

    odds_url = f"https://api.odds-api.io/v3/odds?apiKey={API_KEY}&eventId={event_id}&bookmakers={chosen}"
    try:
        r = requests.get(odds_url, timeout=10)
        if r.status_code == 200:
            odds_data = r.json()
            all_odds.append((home, away, odds_data))
            logger.info(f"Got odds for {home} vs {away} ({idx+1}/{limit})")
        elif r.status_code == 429:
            # Rate limit exceeded
            logger.warning(f"Rate limit hit. Waiting 60 seconds...")
            time.sleep(60)
            # Retry once
            r = requests.get(odds_url, timeout=10)
            if r.status_code == 200:
                odds_data = r.json()
                all_odds.append((home, away, odds_data))
                logger.info(f"Retry: Got odds for {home} vs {away} ({idx+1}/{limit})")
            else:
                logger.warning(f"Retry failed for {event_id}: {r.status_code}")
        else:
            logger.warning(f"Odds for {event_id} failed: {r.status_code} - {r.text[:100]}")
    except Exception as e:
        logger.warning(f"Error for {event_id}: {e}")
    time.sleep(2)  # Be polite

logger.info(f"Got odds for {len(all_odds)} events.")

# ------------------------------------------------------------
# Step 4: Insert into PostgreSQL
# ------------------------------------------------------------
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="sports_db",
    user="postgres",
    password=PG_PASSWORD
)
cur = conn.cursor()
inserted = 0

for home, away, odds in all_odds:
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
    """, (chosen, home, away, home_odds, draw_odds, away_odds, psycopg2.extras.Json(odds)))
    inserted += 1

conn.commit()
cur.close()
conn.close()
logger.info(f"Inserted {inserted} odds.")