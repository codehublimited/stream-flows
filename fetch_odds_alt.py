"""
Odds Fetcher - Fetches odds from Odds-API.io and stores in PostgreSQL
"""

import psycopg2
import psycopg2.extras
import requests
import pandas as pd
from sqlalchemy import create_engine
import logging
import json
from datetime import datetime

# ========== CONFIGURATION ==========
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'sports_db',
    'user': 'postgres',
    'password': 'YOUR_POSTGRES_PASSWORD'   #2026Stream
}

ODDS_API_KEY = 'YOUR_ODDS_API_KEY'   # fe244fad09b14ed3c9d7b63af96aa2d7f780720d5407bb87d1e6afc7b55313e6

# ========== LOGGING ==========
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """Return a PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)

def create_odds_table():
    """Create the odds table if it does not exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id SERIAL PRIMARY KEY,
            match_id TEXT,
            bookmaker VARCHAR(50) NOT NULL,
            home_team VARCHAR(100) NOT NULL,
            away_team VARCHAR(100) NOT NULL,
            home_win_odds FLOAT,
            draw_odds FLOAT,
            away_win_odds FLOAT,
            over_odds FLOAT,
            under_odds FLOAT,
            raw_data JSONB,
            fetched_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Odds table ensured.")

def fetch_odds_from_api(api_key):
    """Fetch odds from Odds-API.io (free tier)."""
    if not api_key or api_key == '':
        logger.warning("No API key provided, skipping fetch.")
        return []
    url = f"https://odds-api.io/api/v1/odds?sport=soccer&apiKey={api_key}"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"Fetched {len(data)} events.")
            return data
        else:
            logger.error(f"API error {resp.status_code}: {resp.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching odds: {e}")
        return []

def store_odds(events, bookmaker_name):
    """Insert odds events into database."""
    if not events:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    inserted = 0
    for ev in events:
        home = ev.get('home_team', 'Unknown')
        away = ev.get('away_team', 'Unknown')
        # Extract odds from the first bookmaker
        bm = ev.get('bookmakers', [{}])[0]
        markets = bm.get('markets', [{}])
        outcomes = markets[0].get('outcomes', []) if markets else []
        home_odds = draw_odds = away_odds = None
        for o in outcomes:
            name = o.get('name', '')
            if name == home:
                home_odds = o.get('price')
            elif name == away:
                away_odds = o.get('price')
            else:
                draw_odds = o.get('price')
        cur.execute("""
            INSERT INTO odds (bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (bookmaker_name, home, away, home_odds, draw_odds, away_odds, psycopg2.extras.Json(ev)))
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Inserted {inserted} odds for {bookmaker_name}.")

def analyze_predictions_vs_odds():
    """Compare predictions with odds (simple sample)."""
    engine = create_engine(
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    preds = pd.read_sql("""
        SELECT DISTINCT ON (match_id) match_id, home_win_prob, draw_prob, away_win_prob
        FROM predictions
        ORDER BY match_id, prediction_date DESC
    """, engine)
    odds_df = pd.read_sql("""
        SELECT DISTINCT ON (bookmaker, home_team, away_team)
               bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds
        FROM odds
        ORDER BY bookmaker, home_team, away_team, fetched_at DESC
    """, engine)
    if preds.empty or odds_df.empty:
        logger.info("No predictions or odds to compare.")
        return
    logger.info(f"Predictions: {len(preds)} rows, Odds: {len(odds_df)} rows")
    logger.info("Sample odds:\n" + odds_df.head(3).to_string())
    logger.info("Sample predictions:\n" + preds.head(3).to_string())

def main():
    logger.info("Starting odds fetcher...")
    create_odds_table()
    events = fetch_odds_from_api(ODDS_API_KEY)
    if events:
        store_odds(events, 'odds-api-io')
    else:
        logger.warning("No odds fetched.")
    analyze_predictions_vs_odds()
    logger.info("Done.")

if __name__ == "__main__":
    main()