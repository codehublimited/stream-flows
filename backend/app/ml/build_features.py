import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
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


def result_label(home_score, away_score):
    if home_score > away_score:
        return "H"
    elif home_score < away_score:
        return "A"
    return "D"


def team_points(home_score, away_score, is_home):
    if home_score == away_score:
        return 1
    home_won = home_score > away_score
    if (is_home and home_won) or (not is_home and not home_won):
        return 3
    return 0


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("match_date").reset_index(drop=True)
    records = []

    # Global home-advantage baseline, computed once from full history.
    # (Using the whole dataset for this single scalar is acceptable - it's
    # a fixed structural fact about the sport/league, not a per-match leak.)
    overall_home_win_rate = (df["home_score"] > df["away_score"]).mean()

    for idx, row in df.iterrows():
        match_date = row["match_date"]
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        league_id = row["league_id"]

        past = df[df["match_date"] < match_date]

        def recent_form(team_id, n=5):
            team_matches = past[
                (past["home_team_id"] == team_id) | (past["away_team_id"] == team_id)
            ].tail(n)
            if team_matches.empty:
                return 1.0, 0.0, 0.0
            pts, gf, ga = [], [], []
            for _, m in team_matches.iterrows():
                is_home = m["home_team_id"] == team_id
                pts.append(team_points(m["home_score"], m["away_score"], is_home))
                gf.append(m["home_score"] if is_home else m["away_score"])
                ga.append(m["away_score"] if is_home else m["home_score"])
            return float(np.mean(pts)), float(np.mean(gf)), float(np.mean(ga))

        home_pts5, home_gf5, home_ga5 = recent_form(home_id, n=5)
        away_pts5, away_gf5, away_ga5 = recent_form(away_id, n=5)
        home_pts10, home_gf10, home_ga10 = recent_form(home_id, n=10)
        away_pts10, away_gf10, away_ga10 = recent_form(away_id, n=10)

        h2h = past[
            ((past["home_team_id"] == home_id) & (past["away_team_id"] == away_id)) |
            ((past["home_team_id"] == away_id) & (past["away_team_id"] == home_id))
        ].tail(5)

        if h2h.empty:
            h2h_home_win_rate = 0.33
        else:
            home_wins = sum(
                1 for _, m in h2h.iterrows()
                if (m["home_team_id"] == home_id and m["home_score"] > m["away_score"]) or
                   (m["away_team_id"] == home_id and m["away_score"] > m["home_score"])
            )
            h2h_home_win_rate = home_wins / len(h2h)

        records.append({
            "match_id": row["id"],
            "league_id": league_id,
            "home_form_pts5": home_pts5,
            "home_goal_diff5": home_gf5 - home_ga5,
            "away_form_pts5": away_pts5,
            "away_goal_diff5": away_gf5 - away_ga5,
            "home_form_pts10": home_pts10,
            "home_goal_diff10": home_gf10 - home_ga10,
            "away_form_pts10": away_pts10,
            "away_goal_diff10": away_gf10 - away_ga10,
            "h2h_home_win_rate": h2h_home_win_rate,
            "home_advantage_baseline": overall_home_win_rate,
            "result": result_label(row["home_score"], row["away_score"]),
        })

    return pd.DataFrame(records)


if __name__ == "__main__":
    matches = load_matches()
    print(f"Loaded {len(matches)} finished matches")
    features = build_features(matches)
    print(f"Built features for {len(features)} matches")
    print(features.head())
    features.to_csv("app/ml/features.csv", index=False)
    print("Saved to app/ml/features.csv")
