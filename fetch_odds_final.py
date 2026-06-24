#!/usr/bin/env python3
"""
Final odds fetcher – recreates table, fetches odds, compares with predictions.
"""

import psycopg2
import psycopg2.extras
from datetime import datetime
import logging
import requests
import pandas as pd
from sqlalchemy import create_engine
import warnings
warnings.filterwarnings('ignore')

# -------- CONFIGURATION --------
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'sports_db',
    'user': 'postgres',
    'password': 'YOUR_POSTGRES_PASSWORD'   # 2026Stream
}

# Get your free API key from https://odds-api.io/ (or leave empty '')
API_KEY = 'YOUR_ODDS_API_KEY'   # fe244fad09b14ed3c9d7b63af96aa2d7f780720d5407bb87d1e6afc7b55313e6

# Optional: use NaijaBet-Api for Nigerian bookmakers (install: pip install NaijaBet-Api)
USE_NAIJABET = False  # Set to True if you install and want to use it

# -------- LOGGING --------
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

# -------- RECREATE ODDS TABLE --------
def recreate_odds_table():
    """Drop and create odds table with correct columns."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS odds CASCADE')
    cur.execute('''
        CREATE TABLE odds (
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
    ''')
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Odds table recreated with correct schema.")

# -------- FETCH FROM ODDS-API.IO --------
def fetch_odds_api(api_key):
    if not api_key or api_key == '':
        logger.warning("No API key provided. Skipping Odds-API.io fetch.")
        return []
    # Odds-API.io endpoint – adjust if needed (check their docs)
    url = f"https://odds-api.io/api/v1/odds?sport=soccer&apiKey={api_key}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Fetched {len(data)} events from Odds-API.io")
            return data
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching odds: {e}")
        return []

# -------- FETCH FROM NAIJABET-API (optional) --------
def fetch_naijabet(bookie_name):
    try:
        from NaijaBet_Api.bookmakers import bet9ja, sportybet, betking
        if bookie_name.lower() == 'bet9ja':
            bk = bet9ja.Bet9ja()
        elif bookie_name.lower() == 'sportybet':
            bk = sportybet.Sportybet()
        elif bookie_name.lower() == 'betking':
            bk = betking.Betking()
        else:
            return []
        matches = bk.get_all()
        logger.info(f"Fetched {len(matches)} matches from {bookie_name}")
        return matches
    except ImportError:
        logger.warning(f"NaijaBet-Api not installed, skipping {bookie_name}")
        return []
    except Exception as e:
        logger.error(f"Error fetching from {bookie_name}: {e}")
        return []

# -------- STORE ODDS --------
def store_odds(events, bookmaker_name, is_commercial=True):
    if not events:
        return
    conn = get_conn()
    cur = conn.cursor()
    inserted = 0
    for event in events:
        if is_commercial:
            # Commercial API structure (Odds-API.io)
            home = event.get('home_team', 'Unknown')
            away = event.get('away_team', 'Unknown')
            bookmakers = event.get('bookmakers', [])
            if not bookmakers:
                continue
            bm = bookmakers[0]  # take first bookmaker
            outcomes = bm.get('markets', [{}])[0].get('outcomes', [])
            home_odds = draw_odds = away_odds = None
            for o in outcomes:
                if o.get('name') == home:
                    home_odds = o.get('price')
                elif o.get('name') == away:
                    away_odds = o.get('price')
                else:
                    draw_odds = o.get('price')
        else:
            # NaijaBet-Api structure: {'home': 4.0, 'draw': 3.75, 'away': 1.92, 'match': 'Team A - Team B'}
            try:
                home, away = event['match'].split(' - ')
            except:
                home, away = 'Unknown', 'Unknown'
            home_odds = event.get('home')
            draw_odds = event.get('draw')
            away_odds = event.get('away')

        cur.execute("""
            INSERT INTO odds (bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (bookmaker_name, home, away, home_odds, draw_odds, away_odds, psycopg2.extras.Json(event)))
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Inserted {inserted} odds for {bookmaker_name}")

# -------- ANALYZE PREDICTIONS VS ODDS --------
def analyze_value_bets():
    engine = create_engine(f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    # Get latest predictions per match
    preds = pd.read_sql("""
        SELECT DISTINCT ON (match_id) match_id, home_win_prob, draw_prob, away_win_prob
        FROM predictions
        ORDER BY match_id, prediction_date DESC
    """, engine)
    # Get latest odds per bookmaker per home/away team pair
    odds = pd.read_sql("""
        SELECT DISTINCT ON (bookmaker, home_team, away_team)
               bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds
        FROM odds
        ORDER BY bookmaker, home_team, away_team, fetched_at DESC
    """, engine)

    if preds.empty or odds.empty:
        logger.info("No predictions or odds to compare.")
        return

    # Convert odds to implied probabilities (remove overround if needed)
    odds['implied_home'] = 1 / odds['home_win_odds']
    odds['implied_draw'] = 1 / odds['draw_odds']
    odds['implied_away'] = 1 / odds['away_win_odds']

    # Print summary
    logger.info(f"Predictions: {len(preds)} rows, Odds: {len(odds)} rows")
    logger.info("Sample odds (first 3):\n" + odds.head(3).to_string())
    logger.info("Sample predictions (first 3):\n" + preds.head(3).to_string())

    # TODO: Join by team names (fuzzy matching) and date to find value bets.
    # For now, just show counts.

# -------- MAIN --------
def run_once():
    logger.info("Starting odds fetch pipeline...")
    # 1. Recreate table
    recreate_odds_table()
    # 2. Fetch commercial odds
    if API_KEY and API_KEY != '':
        commercial_data = fetch_odds_api(API_KEY)
        if commercial_data:
            store_odds(commercial_data, 'odds-api-io', is_commercial=True)
        else:
            logger.warning("No commercial odds fetched.")
    else:
        logger.info("No commercial API key; skipping commercial fetch.")
    # 3. Fetch Nigerian bookmakers (optional)
    if USE_NAIJABET:
        for bookie in ['bet9ja', 'sportybet', 'betking']:
            data = fetch_naijabet(bookie)
            if data:
                store_odds(data, bookie, is_commercial=False)
    # 4. Analyze
    analyze_value_bets()
    logger.info("Pipeline completed.")

if __name__ == '__main__':
    run_once()