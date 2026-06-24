import requests
import psycopg2
import psycopg2.extras
import os
import logging
import time
import json

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

API_KEY = os.environ.get('ODDS_IO_KEY', '')
if not API_KEY:
    logger.error('No API key provided.')
    exit()

PG_PASSWORD = os.environ.get('PG_PASSWORD', '')
if not PG_PASSWORD:
    logger.error('No PostgreSQL password provided.')
    exit()
# Step 1: Get list of sports and find soccer/football
logger.info('Fetching supported sports...')
sports_url = f'https://api.odds-api.io/v3/sports?apiKey={API_KEY}'
try:
    r = requests.get(sports_url, timeout=10)
    if r.status_code != 200:
        logger.error(f'Failed to fetch sports: {r.status_code} - {r.text[:200]}')
        exit()
    sports = r.json()
    logger.info(f'Found {len(sports)} sports.')
    # Find a soccer/football sport
    soccer_sport = None
    for sport in sports:
        name = sport.get('name', '').lower()
        if 'soccer' in name or 'football' in name:
            soccer_sport = sport
            break
    if not soccer_sport:
        logger.error('No soccer/football sport found. Available sports:')
        for s in sports:
            logger.info(f"  {s.get('id')} – {s.get('name')} (slug: {s.get('slug')})")
        exit()
    sport_slug = soccer_sport.get('slug')
    logger.info(f"Using sport: {soccer_sport.get('name')} (slug: {sport_slug})")
except Exception as e:
    logger.error(f'Error fetching sports: {e}')
    exit()

# Step 2: Get events for that sport
logger.info(f'Fetching events for {sport_slug}...')
events_url = f'https://api.odds-api.io/v3/events?sport={sport_slug}&apiKey={API_KEY}'
try:
    r = requests.get(events_url, timeout=30)
    if r.status_code != 200:
        logger.error(f'Failed to fetch events: {r.status_code} - {r.text[:200]}')
        exit()
    events = r.json()
    logger.info(f'Fetched {len(events)} events.')
except Exception as e:
    logger.error(f'Error fetching events: {e}')
    exit()

# Step 3: For each event, get odds
all_odds = []
for idx, ev in enumerate(events):
    event_id = ev.get('id')
    if not event_id:
        continue
    odds_url = f'https://api.odds-api.io/v3/odds?apiKey={API_KEY}&eventId={event_id}'
    try:
        r = requests.get(odds_url, timeout=10)
        if r.status_code == 200:
            odds_data = r.json()
            all_odds.append((ev, odds_data))
            logger.info(f'Got odds for event {event_id} ({idx+1}/{len(events)})')
        else:
            logger.warning(f'Odds for event {event_id} failed: {r.status_code}')
    except Exception as e:
        logger.warning(f'Error for event {event_id}: {e}')
    time.sleep(0.5)

logger.info(f'Got odds for {len(all_odds)} events.')

# Step 4: Insert into database
conn = psycopg2.connect(host='localhost', port=5432, dbname='sports_db', user='postgres', password=PG_PASSWORD)
cur = conn.cursor()
inserted = 0
for ev, odds in all_odds:
    home = ev.get('home_team', 'Unknown')
    away = ev.get('away_team', 'Unknown')
    home_odds = draw_odds = away_odds = None
    # Try to find 1X2 market in the odds response
    if 'bookmakers' in odds:
        for bm in odds.get('bookmakers', []):
            for market in bm.get('markets', []):
                if market.get('market') == '1X2':
                    for outcome in market.get('outcomes', []):
                        if outcome.get('name') == home:
                            home_odds = outcome.get('price')
                        elif outcome.get('name') == away:
                            away_odds = outcome.get('price')
                        else:
                            draw_odds = outcome.get('price')
                    break
            if home_odds is not None:
                break
    cur.execute('''
        INSERT INTO odds (bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds, raw_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', ('odds-api-io', home, away, home_odds, draw_odds, away_odds, psycopg2.extras.Json(odds)))
    inserted += 1

conn.commit()
cur.close()
conn.close()
logger.info(f'Inserted {inserted} odds.')
