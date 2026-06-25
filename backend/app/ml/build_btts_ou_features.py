import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
# Use the LOCAL database explicitly for this build (not STREAMDB)
engine = create_engine(os.getenv("DATABASE_URL"))


def load_matches():
    query = """
        SELECT id, home_team_id, away_team_id, league_id, match_date,
               home_score, away_score, status
        FROM matches
        WHERE status = 'FT' AND home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY match_date ASC
    """
    return pd.read_sql(query, engine)


def team_points(home_score, away_score, is_home):
    if home_score == away_score:
        return 1
    home_won = home_score > away_score
    if (is_home and home_won) or (not is_home and not home_won):
        return 3
    return 0


def build_btts_ou_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("match_date").reset_index(drop=True)
    records = []

    for idx, row in df.iterrows():
        match_date = row["match_date"]
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]

        past = df[df["match_date"] < match_date]

        def recent_stats(team_id, n=10):
            team_matches = past[
                (past["home_team_id"] == team_id) | (past["away_team_id"] == team_id)
            ].tail(n)
            if team_matches.empty:
                return 1.0, 1.2, 1.2, 0.5, 0.5  # pts, gf, ga, btts_rate, over25_rate
            pts, gf, ga, btts, over25 = [], [], [], [], []
            for _, m in team_matches.iterrows():
                is_home = m["home_team_id"] == team_id
                pts.append(team_points(m["home_score"], m["away_score"], is_home))
                this_gf = m["home_score"] if is_home else m["away_score"]
                this_ga = m["away_score"] if is_home else m["home_score"]
                gf.append(this_gf)
                ga.append(this_ga)
                btts.append(1 if (m["home_score"] > 0 and m["away_score"] > 0) else 0)
                over25.append(1 if (m["home_score"] + m["away_score"]) > 2.5 else 0)
            return (float(np.mean(pts)), float(np.mean(gf)), float(np.mean(ga)),
                    float(np.mean(btts)), float(np.mean(over25)))

        home_pts, home_gf, home_ga, home_btts_rate, home_over25_rate = recent_stats(home_id)
        away_pts, away_gf, away_ga, away_btts_rate, away_over25_rate = recent_stats(away_id)

        total_goals = row["home_score"] + row["away_score"]
        btts_label = 1 if (row["home_score"] > 0 and row["away_score"] > 0) else 0
        over25_label = 1 if total_goals > 2.5 else 0

        records.append({
            "match_id": row["id"],
            "league_id": row["league_id"],
            "home_form_pts": home_pts,
            "home_gf": home_gf,
            "home_ga": home_ga,
            "home_btts_rate": home_btts_rate,
            "home_over25_rate": home_over25_rate,
            "away_form_pts": away_pts,
            "away_gf": away_gf,
            "away_ga": away_ga,
            "away_btts_rate": away_btts_rate,
            "away_over25_rate": away_over25_rate,
            "btts": btts_label,
            "over25": over25_label,
        })

    return pd.DataFrame(records)


if __name__ == "__main__":
    matches = load_matches()
    print(f"Loaded {len(matches)} finished matches")
    features = build_btts_ou_features(matches)
    print(f"Built features for {len(features)} matches")
    print()
    print("BTTS distribution:")
    print(features["btts"].value_counts(normalize=True).round(3))
    print()
    print("Over 2.5 distribution:")
    print(features["over25"].value_counts(normalize=True).round(3))
    features.to_csv("app/ml/btts_ou_features.csv", index=False)
    print("\nSaved to app/ml/btts_ou_features.csv")
