import psycopg2
import psycopg2.extras
from datetime import datetime
import logging
import requests
import pandas as pd
from sqlalchemy import create_engine
import json
import os
import concurrent.futures

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'sports_db',
    'user': 'postgres',
    'password': os.environ.get('PG_PASSWORD', '')
}

THE_ODDS_KEY = os.environ.get('THE_ODDS_KEY', '')
ODDS_IO_KEY = os.environ.get('ODDS_IO_KEY', '')

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def fetch_the_odds(api_key):
    if not api_key:
        logger.warning('The Odds API key missing – skipping.')
        return []
    url = 'https://api.odds-api.io/v3/odds?apiKey=' + api_key + ''
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            logger.info('The Odds API: fetched ' + str(len(data)) + ' events.')
            return data
        else:
            logger.error('The Odds API error: ' + str(r.status_code))
            return []
    except Exception as e:
        logger.error('The Odds API exception: ' + str(e))
        return []

def fetch_odds_io(api_key):
    if not api_key:
        logger.warning('Odds-API.io key missing – skipping.')
        return []
    # Adjust URL if needed – check https://odds-api.io/docs
    url = 'https://odds-api.io/api/odds?sport=soccer&apiKey=' + api_key
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            logger.info('Odds-API.io: fetched ' + str(len(data)) + ' events.')
            return data
        else:
            logger.error('Odds-API.io error: ' + str(r.status_code))
            return []
    except Exception as e:
        logger.error('Odds-API.io exception: ' + str(e))
        return []

def store_odds(events, bookmaker_name, source_type):
    if not events:
        return
    conn = get_conn()
    cur = conn.cursor()
    inserted = 0
    for ev in events:
        if source_type == 'the-odds-api':
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
            cur.execute("""
                INSERT INTO odds (bookmaker, home_team, away_team, home_win_odds, draw_odds, away_win_odds, raw_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (bookmaker_name, home, away, home_odds, draw_odds, away_odds, psycopg2.extras.Json(ev)))
            inserted += 1
        elif source_type == 'odds-io':
            home = ev.get('home_team', ev.get('home', 'Unknown'))
            away = ev.get('away_team', ev.get('away', 'Unknown'))
            home_odds = ev.get('home_win', ev.get('home', None))
            draw_odds = ev.get('draw', None)
            away_odds = ev.get('away_win', ev.get('away', None))
            if home_odds is None or draw_odds is None or away_odds is None:
                bm = ev.get('bookmakers', [{}])[0]
                outcomes = bm.get('markets', [{}])[0].get('outcomes', [])
                for o in outcomes:
                    if o.get('name') == home:
                        home_odds = o.get('price')
                    elif o.get('name') == away:
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
    logger.info('Inserted ' + str(inserted) + ' odds from ' + bookmaker_name)

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
    logger.info('Starting dual API odds fetch...')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_the = executor.submit(fetch_the_odds, THE_ODDS_KEY)
        future_io = executor.submit(fetch_odds_io, ODDS_IO_KEY)
        the_events = future_the.result()
        io_events = future_io.result()
    if the_events:
        store_odds(the_events, 'the-odds-api', 'the-odds-api')
    else:
        logger.warning('No odds from The Odds API.')
    if io_events:
        store_odds(io_events, 'odds-api-io', 'odds-io')
    else:
        logger.warning('No odds from Odds-API.io.')
    analyze()
    logger.info('Done.')

if __name__ == '__main__':
    run()
