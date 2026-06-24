import psycopg2
import psycopg2.extras
from datetime import datetime
import logging
import json
import requests
import pandas as pd
from sqlalchemy import create_engine

# ---- Configuration ----
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'sports_db',
    'user': 'postgres',
    'password': ','
}

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

# ---------- Fetch odds from a commercial API (example: The Odds API) ----------
def fetch_odds_commercial(api_key):
    """
    Fetch odds from The Odds API (free tier available).
    You can get an API key from https://the-odds-api.com/
    """
    sport = "soccer"  # or "football"
    regions = "eu"    # or "us", "uk", etc.
    market = "h2h"    # head-to-head (1X2)
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={api_key}&regions={regions}&markets={market}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Fetched {len(data)} events from The Odds API")
            return data
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching from The Odds API: {e}")
        return []

# ---------- Store odds ----------
def store_odds(events, bookmaker_name):
    if not events:
        return
    conn = get_conn()
    cur = conn.cursor()
    inserted = 0
    for event in events:
        # Extract bookmaker odds (take the first bookmaker for simplicity)
        bookmakers = event.get('bookmakers', [])
        if not bookmakers:
            continue
        # Use the first bookmaker that matches our target (or take the first)
        bm = bookmakers[0]
        odds_data = bm.get('markets', [])[0].get('outcomes', [])
        home_odds = draw_odds = away_odds = None
        for outcome in odds_data:
            if outcome['name'] == event['home_team']:
                home_odds = outcome['price']
            elif outcome['name'] == event['away_team']:
                away_odds = outcome['price']
            else:
                draw_odds = outcome['price']  # usually 'Draw'
        # Insert
        cur.execute("""
            INSERT INTO odds (bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            bookmaker_name,
            event['home_team'],
            event['away_team'],
            home_odds,
            draw_odds,
            away_odds,
            psycopg2.extras.Json(event)
        ))
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Inserted {inserted} odds for {bookmaker_name}")

# ---------- Compare with predictions ----------
def analyze_odds_vs_predictions():
    engine = create_engine(f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    preds = pd.read_sql("""
        SELECT DISTINCT ON (match_id) match_id, home_win_prob, draw_prob, away_win_prob
        FROM predictions
        ORDER BY match_id, prediction_date DESC
    """, engine)
    odds = pd.read_sql("""
        SELECT DISTINCT ON (bookmaker, home_team, away_team) 
               bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds
        FROM odds
        ORDER BY bookmaker, home_team, away_team, fetched_at DESC
    """, engine)
    logger.info(f"Predictions: {len(preds)} rows, Odds: {len(odds)} rows")
    # More advanced analysis can be added here

# ---------- Main ----------
def run_once():
    logger.info("Starting odds fetch...")
    # Replace 'YOUR_API_KEY' with your actual The Odds API key
    api_key = "YOUR_API_KEY"  # <-- Get your free key from the-odds-api.com
    events = fetch_odds_commercial(api_key)
    if events:
        store_odds(events, 'the-odds-api')
    else:
        logger.warning("No odds from The Odds API")
    # You can also add scrapers for Bet9ja, Sportybet, Betking here
    analyze_odds_vs_predictions()
    logger.info("Odds fetch completed.")

if __name__ == "__main__":
    run_once()
