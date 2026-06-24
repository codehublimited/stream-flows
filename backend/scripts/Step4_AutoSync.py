"""
================================================================
Auto Sync — API-Football → sports_db
================================================================
Loops through all leagues, pulls fixtures, tracks rate limits,
waits overnight when the daily limit is hit, then continues.

After each cycle (fixtures + stats), automatically runs the
analytics build (team_form, h2h, league_context) from
Step5_BuildAnalytics.py — so the processed analytics layer
always reflects the freshest synced data.

Usage:
    python Step4_AutoSync.py
    python Step4_AutoSync.py --mode fixtures
    python Step4_AutoSync.py --mode all
    python Step4_AutoSync.py --mode all --skip-analytics
================================================================
"""

import os
import sys
import time
import argparse
import requests
import psycopg2
import json
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

# Step5 build functions — analytics layer (team_form, h2h, league_context)
from Step5_BuildAnalytics import (
    ensure_tables,
    build_team_form,
    build_h2h,
    build_league_context,
)

load_dotenv(r"C:\SportsDB\.env")

API_KEY  = os.getenv("API_FOOTBALL_KEY")
DB_HOST  = os.getenv("DB_HOST", "localhost")
DB_PORT  = os.getenv("DB_PORT", "5432")
DB_NAME  = os.getenv("DB_NAME", "sports_db")
DB_USER  = os.getenv("DB_USER", "postgres")
DB_PASS  = os.getenv("DB_PASSWORD", "")

API_BASE = "https://v3.football.api-sports.io"
HEADERS  = {
    "x-apisports-key": API_KEY,
    "x-apisports-host": "v3.football.api-sports.io"
}

SEASONS_TO_SYNC = [2025, 2026]

# All football leagues to sync
FOOTBALL_LEAGUES = {
    "EPL": 39,  "LAL": 140, "SRA": 135,
    "BUN": 78,  "LIG": 61,  "UCL": 2,
    "UEL": 3,   "NPF": 332, "ERE": 88,
    "PPL": 94,  "TSL": 203, "SPL": 179,
}

# ── Logging ─────────────────────────────────────────────────────
LOG_FILE = r"C:\SportsDB\sync_log.txt"

def log(msg, level="INFO"):
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ── DB ──────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )

# ── Rate limit state ────────────────────────────────────────────
remaining_requests = 100

def api_get(endpoint, params=None):
    global remaining_requests
    url = f"{API_BASE}/{endpoint}"
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        remaining_requests = int(r.headers.get("x-ratelimit-requests-remaining", remaining_requests))

        if r.status_code == 429:
            log("Rate limit hit — waiting 60 seconds", "WARN")
            time.sleep(60)
            return api_get(endpoint, params)

        r.raise_for_status()
        data = r.json()
        records = len(data.get("response", []))
        log(f"GET {endpoint} → {records} records | requests left: {remaining_requests}")
        return data.get("response", [])

    except requests.exceptions.HTTPError as e:
        log(f"HTTP error on {endpoint}: {e}", "ERROR")
        return []
    except Exception as e:
        log(f"API error on {endpoint}: {e}", "ERROR")
        return []

# ── Wait until midnight reset ───────────────────────────────────
def wait_for_reset():
    now       = datetime.now()
    tomorrow  = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0)
    wait_secs = (tomorrow - now).total_seconds()
    log(f"Daily limit reached. Sleeping until {tomorrow.strftime('%Y-%m-%d %H:%M:%S')} ({int(wait_secs/3600)}h {int((wait_secs%3600)/60)}m)", "WARN")
    time.sleep(wait_secs)
    log("Woke up — resuming sync")

# ── Upserts ──────────────────────────────────────────────────────
def upsert_team(cur, sport_id, name, short_code, country):
    cur.execute("""
        INSERT INTO teams (sport_id, name, short_code, country)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (sport_id, name) DO UPDATE
            SET short_code = EXCLUDED.short_code,
                country    = EXCLUDED.country
        RETURNING team_id
    """, (sport_id, name, short_code or "", country or ""))
    return cur.fetchone()[0]

def upsert_league(cur, sport_id, name, country, code, season):
    cur.execute("""
        INSERT INTO leagues (sport_id, name, country, season, league_code)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (league_code) DO UPDATE
            SET name    = EXCLUDED.name,
                country = EXCLUDED.country,
                season  = EXCLUDED.season
        RETURNING league_id
    """, (sport_id, name, country or "", str(season), code))
    return cur.fetchone()[0]

def save_raw(cur, data, source):
    cur.execute(
        "INSERT INTO raw_imports (raw_data, source, status) VALUES (%s, %s, 'PENDING') RETURNING raw_id",
        (json.dumps(data), source)
    )
    return cur.fetchone()[0]

def result_code(home, away):
    if home is None or away is None:
        return None
    return "H" if home > away else "A" if home < away else "D"

# ── Sync one league fixtures ────────────────────────────────────
def sync_fixtures(code, api_id, season):
    global remaining_requests

    if remaining_requests <= 2:
        wait_for_reset()

    log(f"Syncing fixtures: {code} (API id {api_id}, season {season})")
    fixtures = api_get("fixtures", {"league": api_id, "season": season})
    if not fixtures:
        log(f"No data returned for {code} season {season}", "WARN")
        return 0

    conn  = get_conn()
    cur   = conn.cursor()
    count = 0

    for f in fixtures:
        try:
            fix    = f["fixture"]
            league = f["league"]
            teams  = f["teams"]
            goals  = f["goals"]
            score  = f["score"]

            raw_id    = save_raw(cur, f, f"fixtures/{code}/{season}")
            league_id = upsert_league(cur, 1, league["name"], league.get("country"), code, season)
            home_id   = upsert_team(cur, 1, teams["home"]["name"], teams["home"].get("code"), league.get("country"))
            away_id   = upsert_team(cur, 1, teams["away"]["name"], teams["away"].get("code"), league.get("country"))

            kick_off   = fix.get("date", "")
            match_date = kick_off[:10] if kick_off else None
            match_time = kick_off[11:16] if kick_off and len(kick_off) > 10 else None

            cur.execute("""
                INSERT INTO matches (
                    match_id, sport_id, league_id,
                    home_team_id, away_team_id,
                    match_date, match_time, venue, status, round, referee,
                    score_home, score_away,
                    ht_score_home, ht_score_away, result
                ) VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (match_id) DO UPDATE SET
                    status        = EXCLUDED.status,
                    score_home    = EXCLUDED.score_home,
                    score_away    = EXCLUDED.score_away,
                    ht_score_home = EXCLUDED.ht_score_home,
                    ht_score_away = EXCLUDED.ht_score_away,
                    result        = EXCLUDED.result
            """, (
                str(fix["id"]), league_id, home_id, away_id,
                match_date, match_time,
                fix.get("venue", {}).get("name", ""),
                fix["status"]["short"],
                league.get("round", ""),
                fix.get("referee", ""),
                goals.get("home"), goals.get("away"),
                score.get("halftime", {}).get("home"),
                score.get("halftime", {}).get("away"),
                result_code(goals.get("home"), goals.get("away"))
            ))

            cur.execute(
                "UPDATE raw_imports SET status='PROCESSED' WHERE raw_id=%s", (raw_id,)
            )
            count += 1

        except Exception as e:
            conn.rollback()
            log(f"Row error in {code} fixture {f.get('fixture',{}).get('id')}: {e}", "ERROR")
            continue

    conn.commit()
    cur.close()
    conn.close()
    log(f"✔ {code} — {count} matches upserted")
    return count

# ── Sync stats for finished matches ─────────────────────────────
def sync_stats():
    global remaining_requests
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        SELECT m.match_id FROM matches m
        LEFT JOIN football_stats fs ON fs.match_id = m.match_id
        WHERE m.status = 'FT' AND fs.match_id IS NULL AND m.sport_id = 1
        LIMIT 20
    """)
    match_ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()

    log(f"Syncing stats for {len(match_ids)} unprocessed matches")

    for mid in match_ids:
        if remaining_requests <= 2:
            wait_for_reset()

        stats = api_get("fixtures/statistics", {"fixture": mid})
        if not stats or len(stats) < 2:
            continue

        def get_stat(ts, name):
            for s in ts.get("statistics", []):
                if s["type"] == name:
                    v = s["value"]
                    if v is None:
                        return None
                    if isinstance(v, str) and v.endswith("%"):
                        return float(v.replace("%", ""))
                    try:
                        return float(v)
                    except:
                        return None
            return None

        h, a = stats[0], stats[1]
        conn = get_conn()
        cur  = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO football_stats (
                    match_id,
                    shots_home, shots_away,
                    shots_on_target_home, shots_on_target_away,
                    corners_home, corners_away,
                    possession_home, possession_away,
                    fouls_home, fouls_away,
                    yellow_cards_home, yellow_cards_away,
                    red_cards_home, red_cards_away
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (match_id) DO NOTHING
            """, (
                mid,
                get_stat(h,"Total Shots"),     get_stat(a,"Total Shots"),
                get_stat(h,"Shots on Goal"),    get_stat(a,"Shots on Goal"),
                get_stat(h,"Corner Kicks"),     get_stat(a,"Corner Kicks"),
                get_stat(h,"Ball Possession"),  get_stat(a,"Ball Possession"),
                get_stat(h,"Fouls"),            get_stat(a,"Fouls"),
                get_stat(h,"Yellow Cards"),     get_stat(a,"Yellow Cards"),
                get_stat(h,"Red Cards"),        get_stat(a,"Red Cards"),
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            log(f"Stats error {mid}: {e}", "ERROR")
        finally:
            cur.close()
            conn.close()

        time.sleep(0.5)

    log("✔ Stats sync done")

# ── Analytics build (Step5) ─────────────────────────────────────
def run_analytics_build():
    """
    Runs the Step5 analytics build (team_form, h2h, league_context)
    using today's date as the snapshot. Wrapped so a failure here
    never kills the sync loop itself.
    """
    log("--- Analytics build starting (team_form, h2h, league_context) ---")
    try:
        conn = get_conn()
        try:
            as_of = date.today().isoformat()
            ensure_tables(conn)
            build_team_form(conn, as_of)
            build_h2h(conn)
            build_league_context(conn, as_of)
        finally:
            conn.close()
        log("--- Analytics build complete ---")
    except Exception as e:
        log(f"Analytics build FAILED: {e}", "ERROR")

# ── Main loop ─────────────────────────────────────────────────────
def main(mode, skip_analytics=False):
    log("="*50)
    log(f"Auto Sync started — mode: {mode} | analytics: {'OFF' if skip_analytics else 'ON'}")
    log("="*50)

    cycle = 0
    while True:
        cycle += 1
        log(f"--- Cycle {cycle} started ---")

        if mode in ("fixtures", "all"):
            for season in SEASONS_TO_SYNC:
                for code, api_id in FOOTBALL_LEAGUES.items():
                    if remaining_requests <= 2:
                        wait_for_reset()
                    sync_fixtures(code, api_id, season)
                    time.sleep(1)

        if mode in ("stats", "all"):
            if remaining_requests <= 2:
                wait_for_reset()
            sync_stats()

        # Chain in the analytics build after fixtures+stats are fresh
        if not skip_analytics:
            run_analytics_build()

        log(f"--- Cycle {cycle} complete. Sleeping 6 hours ---")
        time.sleep(6 * 3600)

# ── Entry ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="fixtures",
                        choices=["fixtures", "stats", "all"],
                        help="What to sync (default: fixtures)")
    parser.add_argument("--skip-analytics", action="store_true",
                        help="Skip the team_form/h2h/league_context build after each cycle")
    args = parser.parse_args()
    try:
        main(args.mode, args.skip_analytics)
    except KeyboardInterrupt:
        log("Sync stopped by user")
        sys.exit(0)
