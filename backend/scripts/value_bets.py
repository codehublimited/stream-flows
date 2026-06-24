import psycopg2
import pandas as pd
from datetime import datetime

PG_PASSWORD = "your_password"  # 2026Stream

def get_data():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="sports_db",
        user="postgres",
        password=PG_PASSWORD
    )

    # Get latest predictions per match
    preds = pd.read_sql("""
        SELECT DISTINCT ON (match_id)
            match_id,
            home_win_prob,
            draw_prob,
            away_win_prob,
            prediction_date
        FROM predictions
        ORDER BY match_id, prediction_date DESC
    """, conn)

    # Get latest odds per event (we'll use the most recent per bookmaker)
    odds = pd.read_sql("""
        SELECT DISTINCT ON (event_id, bookmaker)
            event_id,
            bookmaker,
            home_team,
            away_team,
            home_win_odds,
            draw_odds,
            away_win_odds,
            fetched_at
        FROM odds
        WHERE home_win_odds IS NOT NULL
        ORDER BY event_id, bookmaker, fetched_at DESC
    """, conn)

    conn.close()
    return preds, odds

def main():
    preds, odds = get_data()
    print(f"Predictions: {len(preds)} rows")
    print(f"Odds with values: {len(odds)} rows")

    if odds.empty:
        print("\nNo odds with values found yet. Run the odds fetcher first.")
        return

    # Join on team names (exact match) – we don't have a common ID yet
    # We'll do a simple merge on home_team and away_team
    # This is not perfect but gives an idea
    merged = pd.merge(
        preds,
        odds,
        left_on=['home_team', 'away_team'],
        right_on=['home_team', 'away_team'],
        how='inner'
    )

    if merged.empty:
        print("No matches found between predictions and odds (team names may differ).")
        # Print sample team names to help debug
        print("\nSample predictions teams:")
        print(preds[['home_team', 'away_team']].head(5))
        print("\nSample odds teams:")
        print(odds[['home_team', 'away_team']].head(5))
        return

    # Calculate implied probabilities from odds (with overround adjustment – simple)
    merged['implied_home'] = 1 / merged['home_win_odds']
    merged['implied_draw'] = 1 / merged['draw_odds']
    merged['implied_away'] = 1 / merged['away_win_odds']

    # Calculate value (model probability - implied probability)
    merged['value_home'] = merged['home_win_prob'] - merged['implied_home']
    merged['value_draw'] = merged['draw_prob'] - merged['implied_draw']
    merged['value_away'] = merged['away_win_prob'] - merged['implied_away']

    # Sort by largest positive value (home)
    merged_sorted = merged.sort_values('value_home', ascending=False)

    print("\n=== VALUE BETS (home win) ===\n")
    cols = ['home_team', 'away_team', 'bookmaker', 'home_win_prob', 'implied_home', 'value_home']
    print(merged_sorted[cols].head(10).to_string(index=False))

if __name__ == "__main__":
    main()