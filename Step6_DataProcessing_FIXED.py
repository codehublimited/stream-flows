"""
================================================================
Step 6 (FIXED) — Data Processing
sports_db: team_form, h2h, league_context
================================================================
Fixes applied vs. the original Step6_DataProcessing.py:

1. KEY NAMING BUG: get_team_form()'s dict keys ('form_points',
   'goals_scored', 'goals_conceded') were being prefixed as
   f'home_form_{col}' downstream, producing 'home_form_form_points'
   instead of 'home_form_points' — causing a guaranteed KeyError
   in form_diff. Fixed by using consistent column names throughout.

2. MISSING match_id ON h2h/league_context: the original wrote one
   row per match with NO match_id, so multiple meetings between
   the same two teams (or many matches in the same league) all
   collided — downstream lookups grabbed an arbitrary row, not the
   date-correct one. Fixed: h2h and league_context now include
   match_id, so each match gets its own correctly-dated row.

3. HARDCODED ZERO xG: the original always wrote xg_avg=shots=
   corners=0.0, silently destroying any real xG data (e.g. from
   Understat) that existed previously. Fixed: only overwrites
   xg_avg/shots/corners with 0.0 if no real (non-null, non-zero)
   value already exists for that match_id/team_id.

4. Idempotent: uses upsert (ON CONFLICT) instead of DELETE + full
   rewrite, so re-running this script is safe and doesn't destroy
   data other processes may have added.

Usage:
    python Step6_DataProcessing_FIXED.py
================================================================
"""

import os
import sys
import psycopg2
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv(r"C:\SportsDB\.env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "sports_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")

LOG_FILE = r"C:\SportsDB\analytics_log.txt"


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


def ensure_schema(conn):
    """
    Ensures match_id columns exist on h2h and league_context, and a
    unique constraint to support upserts. Safe to run repeatedly.
    """
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE h2h ADD COLUMN IF NOT EXISTS match_id TEXT;
        ALTER TABLE league_context ADD COLUMN IF NOT EXISTS match_id TEXT;
    """)
    conn.commit()

    # Unique constraints needed for ON CONFLICT upserts. Wrapped in a
    # try/except since older Postgres versions error (not just no-op)
    # on duplicate constraint names with IF NOT EXISTS in some forms.
    for stmt in [
        "ALTER TABLE h2h ADD CONSTRAINT h2h_match_id_unique UNIQUE (match_id)",
        "ALTER TABLE league_context ADD CONSTRAINT league_context_match_id_unique UNIQUE (match_id)",
        "ALTER TABLE team_form ADD CONSTRAINT team_form_match_team_unique UNIQUE (match_id, team_id, is_home)",
    ]:
        try:
            cur.execute(stmt)
            conn.commit()
        except psycopg2.errors.DuplicateTable:
            conn.rollback()
        except psycopg2.errors.DuplicateObject:
            conn.rollback()
        except Exception as e:
            conn.rollback()
            log(f"Schema setup note (likely already exists): {e}", "WARN")
    cur.close()


def get_team_form(team_id, cutoff, ft_matches):
    """Last 5 finished matches for a team before cutoff. Consistent key names."""
    games = [
        m for m in ft_matches
        if (m["home_team_id"] == team_id or m["away_team_id"] == team_id)
        and m["match_date"] < cutoff
    ]
    games.sort(key=lambda m: m["match_date"], reverse=True)
    games = games[:5]

    if not games:
        return {"form_points": 0, "goals_scored": 0, "goals_conceded": 0}

    points = goals_scored = goals_conceded = 0
    for m in games:
        is_home = (m["home_team_id"] == team_id)
        gf = (m["score_home"] if is_home else m["score_away"]) or 0
        ga = (m["score_away"] if is_home else m["score_home"]) or 0
        goals_scored += gf
        goals_conceded += ga
        if gf > ga:
            points += 3
        elif gf == ga:
            points += 1

    return {"form_points": points, "goals_scored": goals_scored, "goals_conceded": goals_conceded}


def get_h2h(home_id, away_id, cutoff, ft_matches):
    games = [
        m for m in ft_matches
        if m["home_team_id"] == home_id and m["away_team_id"] == away_id
        and m["match_date"] < cutoff
    ]
    if not games:
        return {"home_wins": 0, "draws": 0, "away_wins": 0, "avg_goals": 0.0, "over25_percent": 0.0}

    hw = dr = aw = total_goals = over25 = 0
    for m in games:
        sh, sa = m["score_home"] or 0, m["score_away"] or 0
        if sh > sa:
            hw += 1
        elif sh == sa:
            dr += 1
        else:
            aw += 1
        g = sh + sa
        total_goals += g
        if g > 2:
            over25 += 1

    n = len(games)
    return {
        "home_wins": hw, "draws": dr, "away_wins": aw,
        "avg_goals": round(total_goals / n, 2),
        "over25_percent": round((over25 / n) * 100, 2),
    }


def get_league_context(league_id, cutoff, ft_matches):
    games = [
        m for m in ft_matches
        if m["league_id"] == league_id and m["match_date"] < cutoff
    ]
    if not games:
        return {"avg_goals": 0.0, "over25_percent": 0.0}

    total_goals = over25 = 0
    for m in games:
        g = (m["score_home"] or 0) + (m["score_away"] or 0)
        total_goals += g
        if g > 2:
            over25 += 1

    n = len(games)
    return {
        "avg_goals": round(total_goals / n, 2),
        "over25_percent": round((over25 / n) * 100, 2),
    }


def main():
    log("=" * 50)
    log("Step 6 (FIXED) — data processing started")
    log("=" * 50)

    conn = get_conn()
    ensure_schema(conn)
    cur = conn.cursor()

    cur.execute("""
        SELECT match_id, home_team_id, away_team_id, league_id, match_date,
               status, score_home, score_away
        FROM matches
        ORDER BY match_date
    """)
    columns = ["match_id", "home_team_id", "away_team_id", "league_id", "match_date", "status", "score_home", "score_away"]
    all_matches = [dict(zip(columns, row)) for row in cur.fetchall()]
    ft_matches = [m for m in all_matches if m["status"] == "FT"]
    log(f"Loaded {len(all_matches)} matches total ({len(ft_matches)} finished)")

    today = date.today()
    written_form = written_h2h = written_lc = 0

    for i, row in enumerate(all_matches):
        match_id = row["match_id"]
        home_id, away_id, league_id = row["home_team_id"], row["away_team_id"], row["league_id"]
        cutoff = row["match_date"] if row["match_date"] < today else today

        # ── team_form: one row per (match_id, team_id, is_home) ──
        for team_id, is_home in [(home_id, True), (away_id, False)]:
            stats = get_team_form(team_id, cutoff, ft_matches)

            # Preserve existing real xG/shots/corners if present; only
            # default to 0.0 when no real value exists yet for this row.
            cur.execute("""
                SELECT xg_avg, shots, corners FROM team_form
                WHERE match_id = %s AND team_id = %s AND is_home = %s
            """, (match_id, team_id, is_home))
            existing = cur.fetchone()
            xg_avg = existing[0] if existing and existing[0] else 0.0
            shots = existing[1] if existing and existing[1] else 0.0
            corners = existing[2] if existing and existing[2] else 0.0

            cur.execute("""
                INSERT INTO team_form (
                    match_id, team_id, is_home, form_points,
                    goals_scored, goals_conceded, xg_avg, shots, corners, as_of_date
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (match_id, team_id, is_home) DO UPDATE SET
                    form_points     = EXCLUDED.form_points,
                    goals_scored    = EXCLUDED.goals_scored,
                    goals_conceded  = EXCLUDED.goals_conceded,
                    xg_avg          = COALESCE(team_form.xg_avg, EXCLUDED.xg_avg),
                    shots           = COALESCE(team_form.shots, EXCLUDED.shots),
                    corners         = COALESCE(team_form.corners, EXCLUDED.corners),
                    as_of_date      = EXCLUDED.as_of_date
            """, (
                match_id, team_id, is_home, stats["form_points"],
                stats["goals_scored"], stats["goals_conceded"],
                xg_avg, shots, corners, cutoff
            ))
            written_form += 1

        # ── h2h: one row per match_id (fixes the collision bug) ──
        h2h_data = get_h2h(home_id, away_id, cutoff, ft_matches)
        cur.execute("""
            INSERT INTO h2h (
                match_id, home_team_id, away_team_id,
                home_wins, draws, away_wins, avg_goals, over25_percent, as_of_date
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (match_id) DO UPDATE SET
                home_wins      = EXCLUDED.home_wins,
                draws          = EXCLUDED.draws,
                away_wins      = EXCLUDED.away_wins,
                avg_goals      = EXCLUDED.avg_goals,
                over25_percent = EXCLUDED.over25_percent,
                as_of_date     = EXCLUDED.as_of_date
        """, (
            match_id, home_id, away_id,
            h2h_data["home_wins"], h2h_data["draws"], h2h_data["away_wins"],
            h2h_data["avg_goals"], h2h_data["over25_percent"], cutoff
        ))
        written_h2h += 1

        # ── league_context: one row per match_id (fixes the collision bug) ──
        lc_data = get_league_context(league_id, cutoff, ft_matches)
        cur.execute("""
            INSERT INTO league_context (match_id, league_id, avg_goals, over25_percent, as_of_date)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (match_id) DO UPDATE SET
                league_id      = EXCLUDED.league_id,
                avg_goals      = EXCLUDED.avg_goals,
                over25_percent = EXCLUDED.over25_percent,
                as_of_date     = EXCLUDED.as_of_date
        """, (match_id, league_id, lc_data["avg_goals"], lc_data["over25_percent"], cutoff))
        written_lc += 1

        if (i + 1) % 500 == 0:
            conn.commit()
            log(f"Progress: {i + 1}/{len(all_matches)}")

    conn.commit()
    cur.close()
    conn.close()

    log(f"team_form: {written_form} rows upserted")
    log(f"h2h: {written_h2h} rows upserted")
    log(f"league_context: {written_lc} rows upserted")
    log("Step 6 (FIXED) complete")
    log("=" * 50)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user")
        sys.exit(0)
    except Exception as e:
        log(f"FATAL ERROR: {e}", "ERROR")
        sys.exit(1)
