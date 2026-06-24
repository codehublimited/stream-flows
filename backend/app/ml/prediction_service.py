import joblib
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.models.match import Match
from app.models.team import Team

MODEL_PATH = "app/ml/model.joblib"
SCALER_PATH = "app/ml/scaler.joblib"
FEATURE_COLUMNS_PATH = "app/ml/feature_columns.joblib"

_model = None
_scaler = None
_feature_columns = None


def _load_artifacts():
    global _model, _scaler, _feature_columns
    if _model is None:
        _model = joblib.load(MODEL_PATH)
        _scaler = joblib.load(SCALER_PATH)
        _feature_columns = joblib.load(FEATURE_COLUMNS_PATH)
    return _model, _scaler, _feature_columns


def team_points(home_score, away_score, is_home):
    if home_score == away_score:
        return 1
    home_won = home_score > away_score
    if (is_home and home_won) or (not is_home and not home_won):
        return 3
    return 0


def compute_recent_form(db: Session, team_id: int, before_date, n: int):
    matches = (
        db.query(Match)
        .filter(
            ((Match.home_team_id == team_id) | (Match.away_team_id == team_id)),
            Match.match_date < before_date,
            Match.status == "FT",
            Match.home_score.isnot(None),
        )
        .order_by(Match.match_date.desc())
        .limit(n)
        .all()
    )
    if not matches:
        return 1.0, 0.0

    pts, gf, ga = [], [], []
    for m in matches:
        is_home = m.home_team_id == team_id
        pts.append(team_points(m.home_score, m.away_score, is_home))
        gf.append(m.home_score if is_home else m.away_score)
        ga.append(m.away_score if is_home else m.home_score)

    return float(np.mean(pts)), float(np.mean(gf) - np.mean(ga))


def compute_h2h(db: Session, home_id: int, away_id: int, before_date):
    h2h = (
        db.query(Match)
        .filter(
            (
                ((Match.home_team_id == home_id) & (Match.away_team_id == away_id))
                | ((Match.home_team_id == away_id) & (Match.away_team_id == home_id))
            ),
            Match.match_date < before_date,
            Match.status == "FT",
        )
        .order_by(Match.match_date.desc())
        .limit(5)
        .all()
    )
    if not h2h:
        return 0.33

    home_wins = sum(
        1 for m in h2h
        if (m.home_team_id == home_id and m.home_score > m.away_score)
        or (m.away_team_id == home_id and m.away_score > m.home_score)
    )
    return home_wins / len(h2h)


def predict_match(db: Session, match: Match) -> dict:
    model, scaler, feature_columns = _load_artifacts()

    home_pts5, home_gd5 = compute_recent_form(db, match.home_team_id, match.match_date, n=5)
    away_pts5, away_gd5 = compute_recent_form(db, match.away_team_id, match.match_date, n=5)
    home_pts10, home_gd10 = compute_recent_form(db, match.home_team_id, match.match_date, n=10)
    away_pts10, away_gd10 = compute_recent_form(db, match.away_team_id, match.match_date, n=10)
    h2h_rate = compute_h2h(db, match.home_team_id, match.away_team_id, match.match_date)

    overall_home_win_rate = 0.419

    row = {
        "home_form_pts5": home_pts5,
        "home_goal_diff5": home_gd5,
        "away_form_pts5": away_pts5,
        "away_goal_diff5": away_gd5,
        "home_form_pts10": home_pts10,
        "home_goal_diff10": home_gd10,
        "away_form_pts10": away_pts10,
        "away_goal_diff10": away_gd10,
        "h2h_home_win_rate": h2h_rate,
        "home_advantage_baseline": overall_home_win_rate,
    }

    for col in feature_columns:
        if col.startswith("league_"):
            league_id_str = col.replace("league_", "")
            row[col] = 1 if str(match.league_id) == league_id_str else 0

    X = pd.DataFrame([row])[feature_columns]

    if scaler is not None:
        X = scaler.transform(X)

    probabilities = model.predict_proba(X)[0]
    classes = model.classes_

    prob_map = dict(zip(classes, probabilities))
    confidence = float(max(probabilities))

    return {
        "predicted_home_win": float(prob_map.get("H", 0.0)),
        "predicted_draw": float(prob_map.get("D", 0.0)),
        "predicted_away_win": float(prob_map.get("A", 0.0)),
        "confidence": confidence,
    }
