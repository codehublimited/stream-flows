"""
app/workers/run_predictions.py
================================
ML prediction worker — trains a voting ensemble on historical
match results and writes probabilities to the predictions table.

Run with:
    python -m app.workers.run_predictions

Features engineered purely from the matches table:
  - Rolling 5-match form for home/away team (points, GF, GA)
  - Head-to-head record (last 10 meetings)
  - Home advantage flag
  - League average goals context
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, log_loss, classification_report
from xgboost import XGBClassifier
import warnings
warnings.filterwarnings("ignore")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_NAME = "voting_ensemble_v1"
MODEL_VERSION = "1.0"
FORM_WINDOW = 5
H2H_WINDOW = 10


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def get_engine():
    return create_engine(DATABASE_URL)


def encode_result(home_score, away_score):
    if home_score > away_score:
        return 0  # home win
    elif home_score == away_score:
        return 1  # draw
    else:
        return 2  # away win


def build_form(matches_df):
    """
    For each match, compute rolling 5-match form for both teams
    BEFORE that match date (no data leakage).
    Returns a dict keyed by match id.
    """
    matches_df = matches_df.sort_values("match_date").copy()
    matches_df["result"] = matches_df.apply(
        lambda r: encode_result(r["home_score"], r["away_score"]), axis=1
    )

    # Build per-team match history
    team_history = {}  # team_id -> list of (date, gf, ga, points)

    form_rows = {}

    for _, row in matches_df.iterrows():
        mid = row["id"]
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        date = row["match_date"]

        def get_form(team_id):
            history = team_history.get(team_id, [])
            recent = [h for h in history if h["date"] < date][-FORM_WINDOW:]
            if not recent:
                return {"form_pts": 0.0, "form_gf": 0.0, "form_ga": 0.0, "form_n": 0}
            pts = sum(h["pts"] for h in recent)
            gf = sum(h["gf"] for h in recent)
            ga = sum(h["ga"] for h in recent)
            return {"form_pts": pts, "form_gf": gf, "form_ga": ga, "form_n": len(recent)}

        home_form = get_form(home_id)
        away_form = get_form(away_id)
        form_rows[mid] = {"home": home_form, "away": away_form}

        # Update histories AFTER computing form (prevent leakage)
        hg, ag = row["home_score"], row["away_score"]
        h_pts = 3 if hg > ag else (1 if hg == ag else 0)
        a_pts = 3 if ag > hg else (1 if ag == hg else 0)

        team_history.setdefault(home_id, []).append(
            {"date": date, "gf": hg, "ga": ag, "pts": h_pts}
        )
        team_history.setdefault(away_id, []).append(
            {"date": date, "gf": ag, "ga": hg, "pts": a_pts}
        )

    return form_rows


def build_h2h(matches_df):
    """
    For each match, compute H2H record from all PRIOR meetings
    between those two teams (regardless of home/away).
    """
    matches_df = matches_df.sort_values("match_date").copy()
    h2h_rows = {}

    for idx, row in matches_df.iterrows():
        mid = row["id"]
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        date = row["match_date"]

        prior = matches_df[
            (matches_df["match_date"] < date) &
            (
                ((matches_df["home_team_id"] == home_id) & (matches_df["away_team_id"] == away_id)) |
                ((matches_df["home_team_id"] == away_id) & (matches_df["away_team_id"] == home_id))
            )
        ].tail(H2H_WINDOW)

        if len(prior) == 0:
            h2h_rows[mid] = {"h2h_hw": 0.0, "h2h_d": 0.0, "h2h_aw": 0.0, "h2h_avg_goals": 0.0, "h2h_n": 0}
            continue

        hw = aw = d = 0
        total_goals = 0
        for _, p in prior.iterrows():
            hg, ag = p["home_score"], p["away_score"]
            total_goals += hg + ag
            # Normalise: was home_id the home team?
            if p["home_team_id"] == home_id:
                if hg > ag: hw += 1
                elif hg == ag: d += 1
                else: aw += 1
            else:
                if ag > hg: hw += 1
                elif ag == hg: d += 1
                else: aw += 1

        n = len(prior)
        h2h_rows[mid] = {
            "h2h_hw": hw / n,
            "h2h_d": d / n,
            "h2h_aw": aw / n,
            "h2h_avg_goals": total_goals / n,
            "h2h_n": n,
        }

    return h2h_rows


def build_features(matches_df, form_rows, h2h_rows, league_avgs):
    rows = []
    for _, row in matches_df.iterrows():
        mid = row["id"]
        f = form_rows.get(mid, {})
        hf = f.get("home", {})
        af = f.get("away", {})
        h2h = h2h_rows.get(mid, {})
        league_avg = league_avgs.get(row["league_id"], 2.5)

        feat = {
            # Home form
            "home_form_pts":   hf.get("form_pts", 0.0),
            "home_form_gf":    hf.get("form_gf", 0.0),
            "home_form_ga":    hf.get("form_ga", 0.0),
            "home_form_n":     hf.get("form_n", 0),
            # Away form
            "away_form_pts":   af.get("form_pts", 0.0),
            "away_form_gf":    af.get("form_gf", 0.0),
            "away_form_ga":    af.get("form_ga", 0.0),
            "away_form_n":     af.get("form_n", 0),
            # Derived
            "form_diff":       hf.get("form_pts", 0.0) - af.get("form_pts", 0.0),
            "gf_diff":         hf.get("form_gf", 0.0) - af.get("form_gf", 0.0),
            "ga_diff":         hf.get("form_ga", 0.0) - af.get("form_ga", 0.0),
            # H2H
            "h2h_hw":          h2h.get("h2h_hw", 0.0),
            "h2h_d":           h2h.get("h2h_d", 0.0),
            "h2h_aw":          h2h.get("h2h_aw", 0.0),
            "h2h_avg_goals":   h2h.get("h2h_avg_goals", 0.0),
            "h2h_n":           h2h.get("h2h_n", 0),
            # Context
            "league_avg_goals": league_avg,
            "home_advantage":  1.0,  # always 1 — home team perspective
        }
        rows.append(feat)

    return pd.DataFrame(rows)


def main():
    log("=" * 55)
    log("Prediction worker started")
    log("=" * 55)

    engine = get_engine()

    log("Loading matches...")
    matches = pd.read_sql(
        "SELECT * FROM matches WHERE status IN ('FT','AET') "
        "ORDER BY match_date",
        engine
    )
    log(f"  Loaded {len(matches)} finished matches")

    if len(matches) < 50:
        log("Not enough data to train (need 50+).", "ERROR")
        sys.exit(1)

    # League average goals (prior to each match — use global avg as proxy)
    league_avgs = (
        matches.groupby("league_id")
        .apply(lambda x: (x["home_score"] + x["away_score"]).mean())
        .to_dict()
    )

    log("Engineering features (form + H2H)...")
    form_rows = build_form(matches)
    h2h_rows = build_h2h(matches)
    X_all = build_features(matches, form_rows, h2h_rows, league_avgs)
    y_all = matches.apply(
        lambda r: encode_result(r["home_score"], r["away_score"]), axis=1
    ).values

    # ── Honest date-based 80/20 train/eval split ──
    split_idx = int(len(X_all) * 0.8)
    X_fit, X_eval = X_all.iloc[:split_idx], X_all.iloc[split_idx:]
    y_fit, y_eval = y_all[:split_idx], y_all[split_idx:]
    log(f"  Train: {len(X_fit)} matches, Eval: {len(X_eval)} matches")

    scaler_eval = StandardScaler()
    X_fit_s = scaler_eval.fit_transform(X_fit)
    X_eval_s = scaler_eval.transform(X_eval)

    eval_voting = VotingClassifier([
        ("rf",  RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1, class_weight="balanced")),
        ("xgb", XGBClassifier(n_estimators=200, random_state=42, eval_metric="mlogloss")),
        ("lr",  LogisticRegression(max_iter=1000, random_state=42)),
    ], voting="soft")
    eval_voting.fit(X_fit_s, y_fit)

    y_pred  = eval_voting.predict(X_eval_s)
    y_proba = eval_voting.predict_proba(X_eval_s)
    acc = accuracy_score(y_eval, y_pred)
    ll  = log_loss(y_eval, y_proba, labels=[0, 1, 2])
    log(f"HONEST EVAL — accuracy: {acc:.4f}, log-loss: {ll:.4f}")
    log("\n" + classification_report(y_eval, y_pred, target_names=["Home", "Draw", "Away"]))

    # ── Refit on ALL data for production predictions ──
    log("Refitting on full dataset...")
    scaler = StandardScaler()
    X_all_s = scaler.fit_transform(X_all)

    voting = VotingClassifier([
        ("rf",  RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1, class_weight="balanced")),
        ("xgb", XGBClassifier(n_estimators=200, random_state=42, eval_metric="mlogloss")),
        ("lr",  LogisticRegression(max_iter=1000, random_state=42)),
    ], voting="soft")
    voting.fit(X_all_s, y_all)

    probs      = voting.predict_proba(X_all_s)
    confidence = np.max(probs, axis=1)

    # ── Write to predictions table ──
    log("Writing predictions to DB...")
    match_ids = matches["id"].tolist()

    with engine.begin() as conn:
        # Idempotent — delete existing predictions for these matches first
        conn.execute(
            text("DELETE FROM predictions WHERE match_id = ANY(:ids)"),
            {"ids": match_ids}
        )

    records = []
    for i, (_, row) in enumerate(matches.iterrows()):
        records.append({
            "match_id":           int(row["id"]),
            "predicted_home_win": float(probs[i, 0]),
            "predicted_draw":     float(probs[i, 1]),
            "predicted_away_win": float(probs[i, 2]),
            "confidence":         float(confidence[i]),
            "prediction_type":    "match_winner",
            "created_at":         datetime.now(timezone.utc),
        })

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO predictions
                    (match_id, predicted_home_win, predicted_draw,
                     predicted_away_win, confidence, prediction_type, created_at)
                VALUES
                    (:match_id, :predicted_home_win, :predicted_draw,
                     :predicted_away_win, :confidence, :prediction_type, :created_at)
            """),
            records
        )

    log(f"Saved {len(records)} predictions (acc={acc:.4f}, ll={ll:.4f})")
    log("Prediction worker complete")
    log("=" * 55)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user")
        sys.exit(0)
    except Exception as e:
        import traceback
        log(f"FATAL: {e}", "ERROR")
        traceback.print_exc()
        sys.exit(1)