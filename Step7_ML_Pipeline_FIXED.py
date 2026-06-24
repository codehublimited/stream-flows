"""
================================================================
Step 7 (FIXED) — ML Prediction Pipeline
sports_db: train ensemble, evaluate honestly, predict upcoming
================================================================
Fixes applied vs. the original Step7_ML_Pipeline.py:

1. KEY NAMING BUG: form_diff referenced f['home_form_points'], but
   features were stored under f'home_form_{col}' where col was
   already named 'form_points' -> 'home_form_form_points'. Fixed:
   consistent naming throughout (home_form_points, not doubled).

2. ARBITRARY ROW SELECTION: h2h/league_context lookups used
   .iloc[0] on a team/league filter with no date awareness, grabbing
   whichever row happened to load first. Fixed: joins are now by
   match_id directly (Step6_FIXED writes one h2h/league_context row
   per match_id), so every match gets its own correct context.

3. NO EVALUATION: the original trained on 100% of historical data
   with no held-out test set, no accuracy, no log loss — meaning
   there was no way to know if the model was any good. Fixed: a
   date-based train/test split with full evaluation runs before
   predicting on upcoming matches.

4. DEPRECATED PARAM: use_label_encoder was removed in XGBoost 2.0+
   and raises a TypeError if passed. Removed.

5. Idempotent: still deletes + reinserts predictions only for the
   specific match_ids being predicted this run (unchanged from
   original, this part was already correct).

Usage:
    python Step7_ML_Pipeline_FIXED.py
================================================================
"""

import os
import sys
import numpy as np
import pandas as pd
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, log_loss, classification_report
from xgboost import XGBClassifier, XGBRegressor
import warnings
warnings.filterwarnings("ignore")

load_dotenv(r"C:\SportsDB\.env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "sports_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")

LOG_FILE = r"C:\SportsDB\analytics_log.txt"
MODEL_NAME = "voting_ensemble_v2_fixed"
VERSION = "2.0"


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_engine():
    from sqlalchemy import create_engine
    return create_engine(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def encode_result(row):
    if row["status"] != "FT":
        return np.nan
    if row["score_home"] > row["score_away"]:
        return 0  # home win
    elif row["score_home"] == row["score_away"]:
        return 1  # draw
    else:
        return 2  # away win


def build_features(matches, team_form, h2h, league_context, football_stats):
    """
    Builds one feature row per match, joined by match_id (not by
    team_id + arbitrary row selection like the original). This is
    the core correctness fix.
    """
    tf_index = {}
    for _, r in team_form.iterrows():
        tf_index[(r["match_id"], r["team_id"])] = r

    h2h_index = h2h.set_index("match_id") if "match_id" in h2h.columns else None
    lc_index = league_context.set_index("match_id") if "match_id" in league_context.columns else None
    fs_index = football_stats.set_index("match_id") if "match_id" in football_stats.columns else None
    stats_cols = ["shots", "shots_on_target", "corners", "possession", "xg", "fouls", "yellow_cards", "red_cards"]
    form_cols = ["form_points", "goals_scored", "goals_conceded", "xg_avg", "shots", "corners"]
    h2h_cols = ["home_wins", "draws", "away_wins", "avg_goals", "over25_percent"]

    rows = []
    for _, row in matches.iterrows():
        match_id = row["match_id"]
        home_id, away_id = row["home_team_id"], row["away_team_id"]
        f = {}

        if lc_index is not None and match_id in lc_index.index:
            lc = lc_index.loc[match_id]
            f["league_avg_goals"] = lc["avg_goals"]
            f["league_over25_pct"] = lc["over25_percent"]
        else:
            f["league_avg_goals"] = 0.0
            f["league_over25_pct"] = 0.0

        hf = tf_index.get((match_id, home_id))
        for col in form_cols:
            f[f"home_{col}"] = hf[col] if hf is not None and pd.notna(hf[col]) else 0.0

        af = tf_index.get((match_id, away_id))
        for col in form_cols:
            f[f"away_{col}"] = af[col] if af is not None and pd.notna(af[col]) else 0.0

        if h2h_index is not None and match_id in h2h_index.index:
            hh = h2h_index.loc[match_id]
            for col in h2h_cols:
                f[f"h2h_{col}"] = hh[col]
        else:
            for col in h2h_cols:
                f[f"h2h_{col}"] = 0.0

        if fs_index is not None and match_id in fs_index.index:
            fs = fs_index.loc[match_id]
            for col in stats_cols:
                home_val = fs.get(f"{col}_home")
                away_val = fs.get(f"{col}_away")
                f[f"home_stats_{col}"] = float(home_val) if pd.notna(home_val) else 0.0
                f[f"away_stats_{col}"] = float(away_val) if pd.notna(away_val) else 0.0
        else:
            for col in stats_cols:
                f[f"home_stats_{col}"] = 0.0
                f[f"away_stats_{col}"] = 0.0

        f["form_diff"] = f["home_form_points"] - f["away_form_points"]
        f["home_goal_ratio"] = (f["home_goals_scored"] + 1) / (f["home_goals_scored"] + f["home_goals_conceded"] + 2)
        f["away_goal_ratio"] = (f["away_goals_scored"] + 1) / (f["away_goals_scored"] + f["away_goals_conceded"] + 2)

        rows.append(f)

    return pd.DataFrame(rows)


def main():
    log("=" * 50)
    log("Step 7 (FIXED) — ML pipeline started")
    log("=" * 50)

    engine = get_engine()

    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                match_id TEXT NOT NULL,
                home_win_prob FLOAT,
                draw_prob FLOAT,
                away_win_prob FLOAT,
                predicted_home_xg FLOAT,
                predicted_away_xg FLOAT,
                confidence_score FLOAT,
                model_agreement FLOAT,
                model_name VARCHAR(50),
                model_version VARCHAR(20),
                prediction_date TIMESTAMP
            );
        """))
        conn.commit()

    log("Loading data...")
    matches = pd.read_sql("SELECT * FROM matches ORDER BY match_date", engine)
    team_form = pd.read_sql("SELECT * FROM team_form", engine)
    h2h = pd.read_sql("SELECT * FROM h2h", engine)
    league_context = pd.read_sql("SELECT * FROM league_context", engine)
    try:
        football_stats = pd.read_sql("SELECT * FROM football_stats", engine)
    except Exception:
        football_stats = pd.DataFrame()

    matches["target"] = matches.apply(encode_result, axis=1)
    train_df = matches[matches["target"].notna()].copy().sort_values("match_date")
    pred_df = matches[matches["target"].isna()].copy()
    log(f"Train-eligible (finished): {len(train_df)}, Upcoming: {len(pred_df)}")

    if len(train_df) < 50:
        log("Not enough finished matches to train.", "ERROR")
        sys.exit(1)

    log("Engineering features...")
    X_train_raw = build_features(train_df, team_form, h2h, league_context, football_stats)
    y = train_df["target"].astype(int).values

    # ── Honest date-based train/test split (the missing evaluation) ──
    split_idx = int(len(X_train_raw) * 0.8)
    X_fit_raw, X_eval_raw = X_train_raw.iloc[:split_idx], X_train_raw.iloc[split_idx:]
    y_fit, y_eval = y[:split_idx], y[split_idx:]
    log(f"Eval split: fit on {len(X_fit_raw)}, evaluate on {len(X_eval_raw)} (most recent matches)")

    scaler_eval = StandardScaler()
    X_fit_scaled = scaler_eval.fit_transform(X_fit_raw)
    X_eval_scaled = scaler_eval.transform(X_eval_raw)

    eval_rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1, class_weight="balanced")
    eval_xgb = XGBClassifier(n_estimators=100, random_state=42, eval_metric="mlogloss")
    eval_lr = LogisticRegression(max_iter=1000, random_state=42)
    eval_voting = VotingClassifier([("rf", eval_rf), ("xgb", eval_xgb), ("lr", eval_lr)], voting="soft")
    eval_voting.fit(X_fit_scaled, y_fit)

    y_pred = eval_voting.predict(X_eval_scaled)
    y_proba = eval_voting.predict_proba(X_eval_scaled)
    acc = accuracy_score(y_eval, y_pred)
    ll = log_loss(y_eval, y_proba, labels=[0, 1, 2])
    log(f"HONEST EVAL — accuracy: {acc:.4f}, log loss: {ll:.4f}")
    log("\n" + classification_report(y_eval, y_pred, target_names=["Home", "Draw", "Away"]))

    if len(pred_df) == 0:
        log("No upcoming matches to predict. Stopping after evaluation.", "WARN")
        return

    log("Refitting on full historical data for production predictions...")
    X_pred_raw = build_features(pred_df, team_form, h2h, league_context, football_stats)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_raw)
    X_pred_scaled = scaler.transform(X_pred_raw)

    y_home_xg = train_df["score_home"].fillna(0).values
    y_away_xg = train_df["score_away"].fillna(0).values

    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1, class_weight="balanced")
    xgb = XGBClassifier(n_estimators=100, random_state=42, eval_metric="mlogloss")
    lr = LogisticRegression(max_iter=1000, random_state=42)

    # Fit each individually FIRST — VotingClassifier internally clones
    # and fits its own copies, so without this step rf/xgb/lr below
    # remain unfitted and predict_proba() on them crashes.
    rf.fit(X_train_scaled, y)
    xgb.fit(X_train_scaled, y)
    lr.fit(X_train_scaled, y)

    voting = VotingClassifier([("rf", rf), ("xgb", xgb), ("lr", lr)], voting="soft")
    voting.fit(X_train_scaled, y)

    rf_xg_home = RandomForestRegressor(n_estimators=100, random_state=42)
    xgb_xg_home = XGBRegressor(n_estimators=100, random_state=42)
    rf_xg_home.fit(X_train_scaled, y_home_xg)
    xgb_xg_home.fit(X_train_scaled, y_home_xg)

    rf_xg_away = RandomForestRegressor(n_estimators=100, random_state=42)
    xgb_xg_away = XGBRegressor(n_estimators=100, random_state=42)
    rf_xg_away.fit(X_train_scaled, y_away_xg)
    xgb_xg_away.fit(X_train_scaled, y_away_xg)

    def avg_pred(r1, r2, X):
        return (r1.predict(X) + r2.predict(X)) / 2

    probs = voting.predict_proba(X_pred_scaled)
    probs_rf = rf.predict_proba(X_pred_scaled)
    probs_xgb = xgb.predict_proba(X_pred_scaled)
    probs_lr = lr.predict_proba(X_pred_scaled)
    agreement = [
        float(np.mean(np.std([probs_rf[i], probs_xgb[i], probs_lr[i]], axis=0)))
        for i in range(len(X_pred_scaled))
    ]
    confidence = np.max(probs, axis=1)
    home_xg = avg_pred(rf_xg_home, xgb_xg_home, X_pred_scaled)
    away_xg = avg_pred(rf_xg_away, xgb_xg_away, X_pred_scaled)

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM predictions WHERE match_id = ANY(:ids)"),
                     {"ids": pred_df["match_id"].tolist()})
        conn.commit()

    out = pd.DataFrame({
        "match_id": pred_df["match_id"].values,
        "home_win_prob": probs[:, 0],
        "draw_prob": probs[:, 1],
        "away_win_prob": probs[:, 2],
        "predicted_home_xg": home_xg,
        "predicted_away_xg": away_xg,
        "confidence_score": confidence,
        "model_agreement": agreement,
        "model_name": MODEL_NAME,
        "model_version": VERSION,
        "prediction_date": datetime.now(),
    })
    out.to_sql("predictions", engine, if_exists="append", index=False, method="multi")
    log(f"Saved {len(out)} predictions (model_version={VERSION}, eval_accuracy={acc:.4f})")
    log("Step 7 (FIXED) complete")
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
