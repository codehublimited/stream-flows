import requests
import psycopg2
import psycopg2.extras
import logging
import time
import re

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

API_KEY = "fe244fad09b14ed3c9d7b63af96aa2d7f780720d5407bb87d1e6afc7b55313e6"
PG_PASSWORD = "your_postgres_password"  # <-- CHANGE THIS

def get_bookmaker():
    # Try to get a list of bookmakers, but we'll just use the first one with odds
    url = f"https://api.odds-api.io/v3/bookmakers?apiKey={API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            for bm in data:
                if bm.get("active", False):
                    return bm.get("name")
    except:
        pass
    return "bet365"  # fallback

BOOKMAKER = get_bookmaker()
logger.info(f"Using bookmaker: {BOOKMAKER}")

logger.info("Fetching events (only upcoming)...")
events_url = f"https://api.odds-api.io/v3/events?sport=football&apiKey={API_KEY}"
r = requests.get(events_url, timeout=30)
if r.status_code != 200:
    logger.error(f"Events fetch failed: {r.status_code}")
    exit()
all_events = r.json()

# Filter: only non-settled events (upcoming or inplay)
upcoming_events = [ev for ev in all_events if ev.get("status") != "settled"]
logger.info(f"Found {len(upcoming_events)} upcoming events (out of {len(all_events)} total).")

def get_existing_event_ids():
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="sports_db",
        user="postgres", password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT event_id FROM odds WHERE event_id IS NOT NULL")
    rows = cur.fetchall()
    existing = {row[0] for row in rows}
    cur.close()
    conn.close()
    return existing

existing_ids = get_existing_event_ids()
logger.info(f"Already have {len(existing_ids)} events in DB.")

max_per_run = 5
processed_count = 0
to_process = [ev for ev in upcoming_events if ev.get("id") not in existing_ids]

while True:
    if not to_process:
        logger.info("All upcoming events processed. Sleeping 1 hour...")
        time.sleep(3600)
        r = requests.get(events_url, timeout=30)
        if r.status_code == 200:
            all_events = r.json()
            upcoming_events = [ev for ev in all_events if ev.get("status") != "settled"]
            to_process = [ev for ev in upcoming_events if ev.get("id") not in existing_ids]
            logger.info(f"Found {len(to_process)} new upcoming events.")
        continue

    batch = to_process[:max_per_run]
    for ev in batch:
        event_id = ev.get("id")
        if not event_id:
            continue
        home = ev.get("home", "Unknown")
        away = ev.get("away", "Unknown")

        # Try without bookmaker parameter first (returns all bookmakers)
        odds_url = f"https://api.odds-api.io/v3/odds?apiKey={API_KEY}&eventId={event_id}"
        try:
            r = requests.get(odds_url, timeout=10)
            if r.status_code == 200:
                odds_data = r.json()
                home_odds = draw_odds = away_odds = None
                # Check if bookmakers exist
                bookmakers = odds_data.get("bookmakers", {})
                if bookmakers:
                    # Iterate over bookmakers, find the first one with 1X2 market
                    for bm_name, bm_data in bookmakers.items():
                        markets = bm_data.get("markets", [])
                        for market in markets:
                            market_name = market.get("market", "").lower()
                            if market_name in ["1x2", "h2h", "match winner", "full time result"]:
                                outcomes = market.get("outcomes", [])
                                for outcome in outcomes:
                                    if outcome.get("name") == home:
                                        home_odds = outcome.get("price")
                                    elif outcome.get("name") == away:
                                        away_odds = outcome.get("price")
                                    else:
                                        draw_odds = outcome.get("price")
                                break
                        if home_odds is not None:
                            BOOKMAKER = bm_name
                            break
                if home_odds is not None and draw_odds is not None and away_odds is not None:
                    conn = psycopg2.connect(
                        host="localhost", port=5432, dbname="sports_db",
                        user="postgres", password=PG_PASSWORD
                    )
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO odds (bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds, raw_data, event_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (BOOKMAKER, home, away, home_odds, draw_odds, away_odds, psycopg2.extras.Json(odds_data), event_id))
                    conn.commit()
                    cur.close()
                    conn.close()
                    existing_ids.add(event_id)
                    processed_count += 1
                    logger.info(f"Inserted odds for {home} vs {away} (event {event_id}) - total: {processed_count}")
                else:
                    logger.warning(f"No 1X2 odds for {home} vs {away} (event {event_id})")
                    existing_ids.add(event_id)
            elif r.status_code == 429:
                error_msg = r.json().get("error", "")
                match = re.search(r"resets in (\d+) minutes? and (\d+) seconds?", error_msg)
                if match:
                    minutes = int(match.group(1))
                    seconds = int(match.group(2))
                    wait_seconds = minutes * 60 + seconds + 5
                else:
                    wait_seconds = 3600
                logger.warning(f"Rate limit hit. Waiting {wait_seconds} seconds...")
                time.sleep(wait_seconds)
            else:
                logger.warning(f"Odds for {event_id} failed: {r.status_code} - {r.text[:100]}")
        except Exception as e:
            logger.warning(f"Error for {event_id}: {e}")
        time.sleep(2)

    batch_ids = {ev.get("id") for ev in batch}
    to_process = [ev for ev in to_process if ev.get("id") not in batch_ids]
    logger.info(f"Batch done. Processed {len(batch)} events. Total: {processed_count}. Remaining: {len(to_process)}")
    time.sleep(5)
