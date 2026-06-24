"""
================================================================
Step 0 — Project Trace / Diagnostic (READ-ONLY)
sports_db: full pipeline health check
================================================================
Surveys every table in the pipeline and reports real, current
ground truth: row counts, coverage, date ranges, and gaps.

This script makes NO changes to the database — pure read-only
diagnostics, safe to run any time.

Usage:
    python Step0_TraceProject.py
================================================================
"""

import os
import sys
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(r"C:\SportsDB\.env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "sports_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )


def section(title):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def main():
    conn = get_conn()
    cur = conn.cursor()

    print(f"PROJECT TRACE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {DB_NAME} @ {DB_HOST}:{DB_PORT}")

    # ── 1. All tables and row counts ──
    section("1. ALL TABLES — ROW COUNTS")
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [r[0] for r in cur.fetchall()]
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        count = cur.fetchone()[0]
        print(f"  {t:25s} {count:>8,} rows")

    # ── 2. matches breakdown ──
    section("2. MATCHES — STATUS BREAKDOWN")
    cur.execute("""
        SELECT status, COUNT(*), MIN(match_date), MAX(match_date)
        FROM matches GROUP BY status ORDER BY COUNT(*) DESC
    """)
    for status, count, min_d, max_d in cur.fetchall():
        print(f"  {status:15s} {count:>6,} matches   range: {min_d} to {max_d}")

    # ── 3. matches by league ──
    section("3. MATCHES BY LEAGUE")
    cur.execute("""
        SELECT l.league_code, l.name,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE m.status = 'FT') AS finished,
               COUNT(*) FILTER (WHERE m.status != 'FT') AS upcoming
        FROM matches m
        JOIN leagues l ON l.league_id = m.league_id
        GROUP BY l.league_code, l.name
        ORDER BY l.league_code
    """)
    for code, name, total, finished, upcoming in cur.fetchall():
        print(f"  {code:6s} {name:25s} total={total:>5,}  finished={finished:>5,}  upcoming={upcoming:>4,}")

    # ── 4. team_form coverage ──
    section("4. TEAM_FORM COVERAGE")
    cur.execute("SELECT COUNT(*) FROM team_form")
    tf_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM team_form WHERE xg_avg_2y IS NOT NULL")
    tf_xg = cur.fetchone()[0]
    print(f"  team_form rows total:              {tf_total:,}")
    print(f"  team_form rows with real xG:        {tf_xg:,}")

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE m.status = 'FT') AS ft_total,
            COUNT(*) FILTER (WHERE m.status = 'FT' AND tf.match_id IS NOT NULL) AS ft_covered,
            COUNT(*) FILTER (WHERE m.status != 'FT') AS upcoming_total,
            COUNT(*) FILTER (WHERE m.status != 'FT' AND tf.match_id IS NOT NULL) AS upcoming_covered
        FROM matches m
        LEFT JOIN (SELECT DISTINCT match_id FROM team_form) tf ON tf.match_id = m.match_id
    """)
    ft_total, ft_covered, up_total, up_covered = cur.fetchone()
    print(f"  Finished matches: {ft_covered:,}/{ft_total:,} have team_form")
    print(f"  Upcoming matches: {up_covered:,}/{up_total:,} have team_form")

    # ── 5. h2h coverage ──
    section("5. H2H COVERAGE")
    cur.execute("SELECT COUNT(*) FROM h2h")
    h2h_total = cur.fetchone()[0]
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE m.status = 'FT') AS ft_total,
            COUNT(*) FILTER (WHERE m.status = 'FT' AND h.match_id IS NOT NULL) AS ft_covered,
            COUNT(*) FILTER (WHERE m.status != 'FT') AS upcoming_total,
            COUNT(*) FILTER (WHERE m.status != 'FT' AND h.match_id IS NOT NULL) AS upcoming_covered
        FROM matches m
        LEFT JOIN h2h h ON h.match_id = m.match_id
    """)
    ft_total, ft_covered, up_total, up_covered = cur.fetchone()
    print(f"  h2h rows total: {h2h_total:,}")
    print(f"  Finished matches: {ft_covered:,}/{ft_total:,} have h2h")
    print(f"  Upcoming matches: {up_covered:,}/{up_total:,} have h2h")

    # ── 6. league_context coverage ──
    section("6. LEAGUE_CONTEXT COVERAGE")
    cur.execute("SELECT COUNT(*) FROM league_context")
    lc_total = cur.fetchone()[0]
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE m.status = 'FT') AS ft_total,
            COUNT(*) FILTER (WHERE m.status = 'FT' AND lc.match_id IS NOT NULL) AS ft_covered,
            COUNT(*) FILTER (WHERE m.status != 'FT') AS upcoming_total,
            COUNT(*) FILTER (WHERE m.status != 'FT' AND lc.match_id IS NOT NULL) AS upcoming_covered
        FROM matches m
        LEFT JOIN league_context lc ON lc.match_id = m.match_id
    """)
    ft_total, ft_covered, up_total, up_covered = cur.fetchone()
    print(f"  league_context rows total: {lc_total:,}")
    print(f"  Finished matches: {ft_covered:,}/{ft_total:,} have league_context")
    print(f"  Upcoming matches: {up_covered:,}/{up_total:,} have league_context")

    # ── 7. predictions table ──
    section("7. PREDICTIONS TABLE")
    cur.execute("SELECT COUNT(*) FROM predictions")
    pred_total = cur.fetchone()[0]
    print(f"  predictions rows total: {pred_total:,}")
    if pred_total > 0:
        cur.execute("""
            SELECT model_name, model_version, COUNT(*), MIN(generated_at), MAX(generated_at)
            FROM predictions GROUP BY model_name, model_version
            ORDER BY MAX(generated_at) DESC
        """)
        print("  Breakdown by model_name/model_version:")
        for name, version, count, min_g, max_g in cur.fetchall():
            print(f"    {name} / {version}: {count} rows, generated {min_g} to {max_g}")

    # ── 8. other supporting tables ──
    section("8. OTHER SUPPORTING TABLES")
    for t in ["odds", "football_stats", "basketball_stats", "raw_imports"]:
        if t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"  {t}: {cur.fetchone()[0]:,} rows")

    # ── 9. model file check ──
    section("9. SAVED MODEL FILE")
    model_path = r"C:\SportsDB\model_rf_wdl.pkl"
    if os.path.exists(model_path):
        size_kb = os.path.getsize(model_path) / 1024
        mtime = datetime.fromtimestamp(os.path.getmtime(model_path))
        print(f"  Found: {model_path} ({size_kb:.1f} KB, last modified {mtime})")
    else:
        print(f"  NOT FOUND: {model_path}")

    snapshot_path = r"C:\SportsDB\match_features_snapshot.csv"
    if os.path.exists(snapshot_path):
        size_kb = os.path.getsize(snapshot_path) / 1024
        print(f"  Found frozen snapshot: {snapshot_path} ({size_kb:.1f} KB)")

    cur.close()
    conn.close()

    print("\n" + "=" * 70)
    print(" TRACE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
