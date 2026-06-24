"""
================================================================
Step 7 — Fetch xG from Understat, backfill team_form
================================================================
Understat (free, open-source) covers only 5 leagues:
    EPL, La Liga, Bundesliga, Serie A, Ligue 1
Matches are joined to your `matches` table by team name + date,
since Understat has its own internal match IDs.

Leagues outside Understat's coverage (UCL, UEL, NPF, ERE, PPL,
TSL, SPL) are skipped gracefully — their team_form rows simply
keep xg_avg_2y / xga_avg_2y as NULL, which the training script
already handles via dropna().

Requires:
    pip install understatapi

Usage:
    python Step7_FetchXG.py
    python Step7_FetchXG.py --season 2024
================================================================
"""

import os
import sys
import argparse
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
from understatapi import UnderstatClient

load_dotenv(r"C:\SportsDB\.env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "sports_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")

LOG_FILE = r"C:\SportsDB\analytics_log.txt"

# Map our league_code -> Understat league key
UNDERSTAT_LEAGUES = {
    "EPL": "EPL",
    "LAL": "La_Liga",
    "BUN": "Bundesliga",
    "SRA": "Serie_A",
    "LIG": "Ligue_1",
}


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )


# Understat uses short/common club names; our DB often has full official
# names. Map Understat's short form -> our DB's form so normalization
# converges on the same string. Add to this as new mismatches turn up.
# Understat uses short/common club names; our DB often has full official
# names (or, in some cases, mangled German special characters from an
# earlier import). Map the short/garbled form -> a single canonical
# ASCII form so both sources converge on the same key.
NAME_ALIASES = {
    # Serie A
    "verona": "hellas verona",
    "roma": "as roma",
    "parma calcio 1913": "parma",
    # Ligue 1
    "brest": "stade brestois 29",
    # La Liga
    "real valladolid": "valladolid",
    # Bundesliga — Understat short names -> canonical form
    "bayern munich": "bayern munchen",
    "borussia monchengladbach": "borussia monchengladbach",
    "borussia mgladbach": "borussia monchengladbach",
    "rb leipzig": "rasenballsport leipzig",
    "mainz 05": "fsv mainz 05",
    "st pauli": "st pauli",
    "fc st pauli": "st pauli",
    "heidenheim": "1 heidenheim",
    "1 fc heidenheim": "1 heidenheim",
    "hoffenheim": "1899 hoffenheim",
    "freiburg": "sc freiburg",
    "wolfsburg": "vfl wolfsburg",
    "bochum": "vfl bochum",
    "augsburg": "fc augsburg",
}


def normalize_name(name):
    """Loose normalization for fuzzy team-name matching across sources."""
    if not name:
        return ""

    cleaned = name.lower()

    # Collapse German umlauts (and mangled/garbled encodings of them seen
    # in our DB, e.g. 'ⁿ' standing in for 'u', '÷' standing in for 'o')
    # down to plain ASCII, so "München"/"Mⁿnchen"/"Munich"-style variants
    # all converge on the same spelling.
    umlaut_map = {
        "ü": "u", "Ü": "u", "ⁿ": "u",
        "ö": "o", "Ö": "o", "÷": "o",
        "ä": "a", "Ä": "a",
        "é": "e", "è": "e",
    }
    for src, dst in umlaut_map.items():
        cleaned = cleaned.replace(src, dst)

    cleaned = (
        cleaned
        .replace(" fc", "")
        .replace("fc ", "")
        .replace(".", "")
        .replace("-", " ")
        .strip()
    )
    cleaned = " ".join(cleaned.split())  # collapse repeated whitespace

    return NAME_ALIASES.get(cleaned, cleaned)


def build_match_lookup(conn, league_code):
    """
    Build a lookup: (normalized_home_name, normalized_away_name) -> list of (match_date, match_id)
    for our own matches table, scoped to one league. Date is matched separately
    with a tolerance window, since Understat's UTC timestamps can roll over to a
    different calendar day than our own match_date depending on kickoff time.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT m.match_id, m.match_date, ht.name, at.name
        FROM matches m
        JOIN teams ht ON ht.team_id = m.home_team_id
        JOIN teams at ON at.team_id = m.away_team_id
        JOIN leagues l ON l.league_id = m.league_id
        WHERE l.league_code = %s AND m.status = 'FT'
    """, (league_code,))
    rows = cur.fetchall()
    cur.close()

    lookup = {}
    for match_id, match_date, home_name, away_name in rows:
        key = (normalize_name(home_name), normalize_name(away_name))
        lookup.setdefault(key, []).append((match_date, match_id))
    return lookup


def find_match_id(lookup, home_name, away_name, match_date_str, tolerance_days=1):
    """
    Find a match_id for a (home, away) pair within +/- tolerance_days of the
    given date. Returns None if no candidate is close enough.
    """
    key = (home_name, away_name)
    candidates = lookup.get(key)
    if not candidates:
        return None

    try:
        target_date = datetime.strptime(match_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    best_match = None
    best_diff = None
    for candidate_date, match_id in candidates:
        diff = abs((candidate_date - target_date).days)
        if diff <= tolerance_days and (best_diff is None or diff < best_diff):
            best_diff = diff
            best_match = match_id

    return best_match


def fetch_understat_matches(client, understat_league, season):
    """Pull all match data for a league/season from Understat."""
    league = client.league(league=understat_league)
    return league.get_match_data(season=str(season))


def main(season):
    log("=" * 50)
    log(f"xG fetch started — season {season}")
    log("=" * 50)

    client = UnderstatClient()
    conn = get_conn()

    total_matched = 0
    total_unmatched = 0

    for league_code, understat_key in UNDERSTAT_LEAGUES.items():
        log(f"--- {league_code} ({understat_key}) ---")

        lookup = build_match_lookup(conn, league_code)
        log(f"  Built lookup with {len(lookup)} local matches for {league_code}")

        try:
            understat_matches = fetch_understat_matches(client, understat_key, season)
        except Exception as e:
            log(f"  Understat fetch failed for {understat_key}: {e}", "ERROR")
            continue

        log(f"  Understat returned {len(understat_matches)} matches")

        cur = conn.cursor()
        matched = 0
        unmatched = 0

        for um in understat_matches:
            try:
                home_name = normalize_name(um.get("h", {}).get("title") or um.get("home_team", ""))
                away_name = normalize_name(um.get("a", {}).get("title") or um.get("away_team", ""))
                match_date_raw = um.get("datetime", "")
                match_date = match_date_raw[:10] if match_date_raw else None
                home_xg = um.get("xG", {}).get("h") if isinstance(um.get("xG"), dict) else um.get("home_xG")
                away_xg = um.get("xG", {}).get("a") if isinstance(um.get("xG"), dict) else um.get("away_xG")

                if not match_date or home_xg is None or away_xg is None:
                    unmatched += 1
                    continue

                key = (home_name, away_name, match_date)
                match_id = find_match_id(lookup, home_name, away_name, match_date)

                if not match_id:
                    unmatched += 1
                    if unmatched <= 8:  # cap noise, just show a sample
                        log(f"  UNMATCHED: '{home_name}' vs '{away_name}' on {match_date}", "WARN")
                    continue

                # Update home team's row in team_form (real column: xg_avg,
                # no separate xga column exists in the current schema —
                # xg_avg simply holds that team's own xG for this match)
                cur.execute("""
                    UPDATE team_form
                    SET xg_avg = %s
                    WHERE match_id = %s AND is_home = true
                """, (float(home_xg), match_id))

                # Update away team's row in team_form
                cur.execute("""
                    UPDATE team_form
                    SET xg_avg = %s
                    WHERE match_id = %s AND is_home = false
                """, (float(away_xg), match_id))

                matched += 1

            except Exception as e:
                log(f"  Row error: {e}", "ERROR")
                unmatched += 1
                continue

        conn.commit()
        cur.close()
        log(f"  {league_code}: matched {matched}, unmatched {unmatched}")
        total_matched += matched
        total_unmatched += unmatched

    conn.close()
    log(f"xG fetch complete — total matched: {total_matched}, unmatched: {total_unmatched}")
    log("Note: UCL, UEL, NPF, ERE, PPL, TSL, SPL are not covered by Understat — "
        "their xg_avg_2y/xga_avg_2y will remain NULL.", "WARN")
    log("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch xG from Understat and backfill team_form")
    parser.add_argument("--season", type=int, default=2024,
                        help="Season start year, e.g. 2024 for 2024/25 (default: 2024)")
    args = parser.parse_args()

    try:
        main(args.season)
    except KeyboardInterrupt:
        log("xG fetch stopped by user")
        sys.exit(0)
    except Exception as e:
        log(f"FATAL ERROR: {e}", "ERROR")
        sys.exit(1)
