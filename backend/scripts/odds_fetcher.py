import psycopg2
import psycopg2.extras
from datetime import datetime
import logging
import requests
import pandas as pd
from sqlalchemy import create_engine
import json
import os

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'sports_db',
    'user': 'postgres',
    'password': os.environ.get('PG_PASSWORD', '')
}

API_KEY = os.environ.get('263f8cb36f4ca320b8050154fef76c1e', '')

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def fetch_odds(api_key):
    if not api_key:
        logger.warning('No API key provided – skipping fetch.')
        return []
    url = 'https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey=' + api_key
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            logger.info('Fetched ' + str(len(data)) + ' events.')
            return data
        else:
            logger.error('API error: ' + str(r.status_code))
            return []
    except Exception as e:
        logger.error('Error: ' + str(e))
        return []

def store_odds(events, bookmaker_name):
    if not events:
        return
    conn = get_conn()
    cur = conn.cursor()
    inserted = 0
    for ev in events:
        home = ev.get('home_team', 'Unknown')
        away = ev.get('away_team', 'Unknown')
        bm = ev.get('bookmakers', [{}])[0]
        outcomes = bm.get('markets', [{}])[0].get('outcomes', [])
        home_odds = draw_odds = away_odds = None
        for o in outcomes:
            if o.get('name') == home:
                home_odds = o.get('price')
            elif o.get('name') == away:
                away_odds = o.get('price')
            else:
                draw_odds = o.get('price')
        cur.execute('''
            INSERT INTO odds (bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (bookmaker_name, home, away, home_odds, draw_odds, away_odds, psycopg2.extras.Json(ev)))
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    logger.info('Inserted ' + str(inserted) + ' odds for ' + bookmaker_name)

def analyze():
    engine = create_engine('postgresql://' + DB_CONFIG['user'] + ':' + DB_CONFIG['password'] + '@' + DB_CONFIG['host'] + ':' + str(DB_CONFIG['port']) + '/' + DB_CONFIG['database'])
    preds = pd.read_sql('SELECT DISTINCT ON (match_id) match_id, home_win_prob, draw_prob, away_win_prob FROM predictions ORDER BY match_id, prediction_date DESC', engine)
    odds = pd.read_sql('SELECT DISTINCT ON (bookmaker, home_team, away_team) bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds FROM odds ORDER BY bookmaker, home_team, away_team, fetched_at DESC', engine)
    if preds.empty or odds.empty:
        logger.info('No predictions or odds to compare.')
    else:
        logger.info('Predictions: ' + str(len(preds)) + ', Odds: ' + str(len(odds)))
        logger.info('Sample odds:\n' + odds.head(3).to_string())
        logger.info('Sample predictions:\n' + preds.head(3).to_string())

def run():
    logger.info('Starting odds fetch...')
    events = fetch_odds(API_KEY)
    if events:
        store_odds(events, 'odds-api-io')
    else:
        logger.warning('No odds fetched.')
    analyze()
    logger.info('Done.')

if __name__ == '__main__':
    run()
