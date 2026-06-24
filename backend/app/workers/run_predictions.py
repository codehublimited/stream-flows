"""
app/workers/run_predictions.py
================================
ML prediction worker — trains a voting ensemble on historical
match results and writes probabilities to the predictions table.

Features:
  - ELO ratings (updates after every match, no leakage)
  - Rolling 5-match form (points, GF, GA) split home/away
  - Head-to-head record (last 10 meetings)
  - League average goals context
  - Cumulative league points at match date

Run with:
    python -m app.workers.run_predictions
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
FORM_WINDOW  = 5
H2H_WINDOW   = 10

# ELO constants
ELO_BASE      = 1500.0
ELO_K         = 32.0
ELO_HOME_ADV  = 50.0  # home team starts with +50 ELO advantage


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


# ─────────────────────────────────────────────
# ELO
# ─────────────────────────────────────────────

def expected_score(rating_a, rating_b):
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def build_elo(matches_df):
    """
    Compute ELO rating for each team BEFORE each match.
    Returns dict keyed by match id:
      { match_id: { home_elo, away_elo, elo_diff } }
    """
    matches_df = matches_df.sort_values("match_date").copy()
    ratings = {}  # team_id -> current ELO

    elo_rows = {}

    for _, row in matches_df.iterrows():
        mid     = row["id"]
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]

        h_elo = ratings.get(home_id, ELO_BASE)
        a_elo = ratings.get(away_id, ELO_BASE)

        # Record BEFORE update (no leakage)
        elo_rows[mid] = {
            "home_elo":  h_elo,
            "away_elo":  a_elo,
            "elo_diff":  h_elo - a_elo,
        }

        # Update ratings after match
        hg, ag = row["home_score"], row["away_score"]
        if hg > ag:
            h_actual, a_actual = 1.0, 0.0
        elif hg == ag:
            h_actual, a_actual = 0.5, 0.5
        else:
            h_actual, a_actual = 0.0, 1.0

        h_exp = expected_score(h_elo + ELO_HOME_ADV, a_elo)
        a_exp = 1.0 - h_exp

        ratings[home_id] = h_elo + ELO_K * (h_actual - h_exp)
        ratings[away_id] = a_elo + ELO_K * (a_actual - a_exp)

    return elo_rows


# ─────────────────────────────────────────────
# Form (home/away split)
# ─────────────────────────────────────────────

def build_form(matches_df):
    """
    Rolling form split into home form and away form separately.
    No leakage — only matches strictly before current match date.
    """
    matches_df = matches_df.sort_values("match_date").copy()

    # team_id -> list of { date, gf, ga, pts, is_home }
    team_history = {}
    form_rows    = {}

    for _, row in matches_df.iterrows():
        mid     = row["id"]
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        date    = row["match_date"]

        def get_form(team_id, playing_home):
            history = team_history.get(team_id, [])
            prior   = [h for h in history if h["date"] < date]

            # Overall form (last 5)
            recent = prior[-FORM_WINDOW:]
            overall = {
                "form_pts": sum(h["pts"] for h in recent),
                "form_gf":  sum(h["gf"]  for h in recent),
                "form_ga":  sum(h["ga"]  for h in recent),
                "form_n":   len(recent),
            } if recent else {"form_pts": 0.0, "form_gf": 0.0, "form_ga": 0.0, "form_n": 0}

            # Venue-specific form (last 5 home or away)
            venue_hist = [h for h in prior if h["is_home"] == playing_home][-FORM_WINDOW:]
            venue = {
                "venue_pts": sum(h["pts"] for h in venue_hist),
                "venue_gf":  sum(h["gf"]  for h in venue_hist),
                "venue_ga":  sum(h["ga"]  for h in venue_hist),
                "venue_n":   len(venue_hist),
            } if venue_hist else {"venue_pts": 0.0, "venue_gf": 0.0, "venue_ga": 0.0, "venue_n": 0}

            return {**overall, **venue}

        form_rows[mid] = {
            "home": get_form(home_id, playing_home=True),
            "away": get_form(away_id, playing_home=False),
        }

        hg, ag  = row["home_score"], row["away_score"]
        h_pts   = 3 if hg > ag else (1 if hg == ag else 0)
        a_pts   = 3 if ag > hg else (1 if ag == hg else 0)

        team_history.setdefault(home_id, []).append(
            {"date": date, "gf": hg, "ga": ag, "pts": h_pts, "is_home": True}
        )
        team_history.setdefault(away_id, []).append(
            {"date": date, "gf": ag, "ga": hg, "pts": a_pts, "is_home": False}
        )

    return form_rows


# ─────────────────────────────────────────────
# H2H
# ─────────────────────────────────────────────

def build_h2h(matches_df):
    matches_df = matches_df.sort_values("match_date").copy()
    h2h_rows   = {}

    for _, row in matches_df.iterrows():
        mid     = row["id"]
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        date    = row["match_date"]

        prior = matches_df[
            (matches_df["match_date"] < date) &
            (
                ((matches_df["home_team_id"] == home_id) & (matches_df["away_team_id"] == away_id)) |
                ((matches_df["home_team_id"] == away_id) & (matches_df["away_team_id"] == home_id))
            )
        ].tail(H2H_WINDOW)

        if len(prior) == 0:
            h2h_rows[mid] = {
                "h2h_hw": 0.0, "h2h_d": 0.0, "h2h_aw": 0.0,
                "h2h_avg_goals": 0.0, "h2h_n": 0
            }
            continue

        hw = aw = d = 0
        total_goals = 0
        for _, p in prior.iterrows():
            hg, ag = p["home_score"], p["away_score"]
            total_goals += hg + ag
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
            "h2h_hw":         hw / n,
            "h2h_d":          d  / n,
            "h2h_aw":         aw / n,
            "h2h_avg_goals":  total_goals / n,
            "h2h_n":          n,
        }

    return h2h_rows


# ─────────────────────────────────────────────
# Cumulative points (league position proxy)
# ─────────────────────────────────────────────

def build_cumulative_points(matches_df):
    """
    For each match, how many league points does each team have
    accumulated so far this season (before this match).
    """
    matches_df = matches_df.sort_values("match_date").copy()
    cum_pts    = {}   # (team_id, league_id) -> points so far
    cp_rows    = {}

    for _, row in matches_df.iterrows():
        mid      = row["id"]
        home_id  = row["home_team_id"]
        away_id  = row["away_team_id"]
        league   = row["league_id"]

        h_key = (home_id, league)
        a_key = (away_id, league)

        cp_rows[mid] = {
            "home_cum_pts": cum_pts.get(h_key, 0),
            "away_cum_pts": cum_pts.get(a_key, 0),
            "cum_pts_diff": cum_pts.get(h_key, 0) - cum_pts.get(a_key, 0),
        }

        hg, ag = row["home_score"], row["away_score"]
        h_pts  = 3 if hg > ag else (1 if hg == ag else 0)
        a_pts  = 3 if ag > hg else (1 if ag == hg else 0)

        cum_pts[h_key] = cum_pts.get(h_key, 0) + h_pts
        cum_pts[a_key] = cum_pts.get(a_key, 0) + a_pts

    return cp_rows


# ─────────────────────────────────────────────
# Feature assembly
# ─────────────────────────────────────────────

def build_features(matches_df, elo_rows, form_rows, h2h_rows, cp_rows, league_avgs):
    rows = []
    for _, row in matches_df.iterrows():
        mid  = row["id"]
        elo  = elo_rows.get(mid, {})
        f    = form_rows.get(mid, {})
        hf   = f.get("home", {})
        af   = f.get("away", {})
        h2h  = h2h_rows.get(mid, {})
        cp   = cp_rows.get(mid, {})
        league_avg = league_avgs.get(row["league_id"], 2.5)

        feat = {
            # ELO
            "home_elo":         elo.get("home_elo",  ELO_BASE),
            "away_elo":         elo.get("away_elo",  ELO_BASE),
            "elo_diff":         elo.get("elo_diff",  0.0),

            # Overall form
            "home_form_pts":    hf.get("form_pts",   0.0),
            "home_form_gf":     hf.get("form_gf",    0.0),
            "home_form_ga":     hf.get("form_ga",    0.0),
            "home_form_n":      hf.get("form_n",     0),
            "away_form_pts":    af.get("form_pts",   0.0),
            "away_form_gf":     af.get("form_gf",    0.0),
            "away_form_ga":     af.get("form_ga",    0.0),
            "away_form_n":      af.get("form_n",     0),

            # Venue-specific form
            "home_venue_pts":   hf.get("venue_pts",  0.0),
            "home_venue_gf":    hf.get("venue_gf",   0.0),
            "home_venue_ga":    hf.get("venue_ga",   0.0),
            "away_venue_pts":   af.get("venue_pts",  0.0),
            "away_venue_gf":    af.get("venue_gf",   0.0),
            "away_venue_ga":    af.get("venue_ga",   0.0),

            # Derived form
            "form_diff":        hf.get("form_pts",   0.0) - af.get("form_pts",  0.0),
            "gf_diff":          hf.get("form_gf",    0.0) - af.get("form_gf",   0.0),
            "ga_diff":          hf.get("form_ga",    0.0) - af.get("form_ga",   0.0),
            "venue_pts_diff":   hf.get("venue_pts",  0.0) - af.get("venue_pts", 0.0),

            # H2H
            "h2h_hw":           h2h.get("h2h_hw",        0.0),
            "h2h_d":            h2h.get("h2h_d",         0.0),
            "h2h_aw":           h2h.get("h2h_aw",        0.0),
            "h2h_avg_goals":    h2h.get("h2h_avg_goals", 0.0),
            "h2h_n":            h2h.get("h2h_n",         0),

            # Cumulative points
            "home_cum_pts":     cp.get("home_cum_pts",  0),
            "away_cum_pts":     cp.get("away_cum_pts",  0),
            "cum_pts_diff":     cp.get("cum_pts_diff",  0),

            # Context
            "league_avg_goals": league_avg,
            "home_advantage":   1.0,
        }
        rows.append(feat)

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# Per-league model training
# ─────────────────────────────────────────────

def train_and_predict_per_league(matches, X_all, y_all):
    """
    Train a separate model for each league.
    Eval set = last 20% of matches per league (by date).
    Returns: probs array (len = len(matches)), eval metrics dict
    """
    all_probs   = np.zeros((len(matches), 3))
    all_correct = []
    league_metrics = {}

    league_ids = matches["league_id"].unique()

    for lid in league_ids:
        mask    = (matches["league_id"] == lid).values
        idx     = np.where(mask)[0]
        X_lg    = X_all.iloc[idx]
        y_lg    = y_all[idx]
        m_lg    = matches.iloc[idx]

        split   = int(len(X_lg) * 0.8)
        if split < 20:
            log(f"  League {lid}: not enough data ({len(X_lg)}), skipping.", "WARN")
            continue

        X_fit, X_eval = X_lg.iloc[:split], X_lg.iloc[split:]
        y_fit, y_eval = y_lg[:split],       y_lg[split:]

        scaler   = StandardScaler()
        X_fit_s  = scaler.fit_transform(X_fit)
        X_eval_s = scaler.transform(X_eval)

        model = VotingClassifier([
            ("rf",  RandomForestClassifier(n_estimators=200, random_state=42,
                                           n_jobs=-1, class_weight="balanced")),
            ("xgb", XGBClassifier(n_estimators=200, random_state=42,
                                  eval_metric="mlogloss")),
            ("lr",  LogisticRegression(max_iter=1000, random_state=42)),
        ], voting="soft")
        model.fit(X_fit_s, y_fit)

        y_pred  = model.predict(X_eval_s)
        y_proba = model.predict_proba(X_eval_s)
        acc     = accuracy_score(y_eval, y_pred)
        ll      = log_loss(y_eval, y_proba, labels=[0, 1, 2])

        league_metrics[lid] = {"acc": acc, "ll": ll, "n_eval": len(y_eval)}
        log(f"  League {lid}: acc={acc:.4f}, log-loss={ll:.4f} ({len(y_eval)} eval matches)")

        # Store eval predictions back into full array
        eval_global_idx = idx[split:]
        all_probs[eval_global_idx] = y_proba

        all_correct.extend(list(zip(eval_global_idx, y_eval, y_pred)))

    return all_probs, all_correct, league_metrics


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    log("=" * 55)
    log("Prediction worker started")
    log("=" * 55)

    engine = get_engine()

    log("Loading matches...")
    matches = pd.read_sql(
        "SELECT * FROM matches WHERE status IN ('FT','AET') ORDER BY match_date",
        engine
    )
    log(f"  Loaded {len(matches)} finished matches across "
        f"{matches['league_id'].nunique()} leagues")

    if len(matches) < 50:
        log("Not enough data to train (need 50+).", "ERROR")
        sys.exit(1)

    league_avgs = (
        matches.groupby("league_id")
        .apply(lambda x: (x["home_score"] + x["away_score"]).mean())
        .to_dict()
    )

    log("Engineering features (ELO + form + H2H + cumulative points)...")
    elo_rows  = build_elo(matches)
    form_rows = build_form(matches)
    h2h_rows  = build_h2h(matches)
    cp_rows   = build_cumulative_points(matches)

    X_all = build_features(matches, elo_rows, form_rows, h2h_rows, cp_rows, league_avgs)
    y_all = matches.apply(
        lambda r: encode_result(r["home_score"], r["away_score"]), axis=1
    ).values

    log(f"  Feature matrix: {X_all.shape[0]} rows x {X_all.shape[1]} features")

    # ── Per-league models ──
    log("Training per-league models...")
    all_probs, all_correct, league_metrics = train_and_predict_per_league(
        matches, X_all, y_all
    )

    # Overall honest accuracy across all eval sets
    if all_correct:
        y_true_all = [x[1] for x in all_correct]
        y_pred_all = [x[2] for x in all_correct]
        overall_acc = accuracy_score(y_true_all, y_pred_all)
        log(f"OVERALL HONEST ACCURACY: {overall_acc:.4f} across "
            f"{len(y_true_all)} eval matches")
        log("\n" + classification_report(
            y_true_all, y_pred_all, target_names=["Home", "Draw", "Away"]
        ))

    # ── Store eval-set predictions ──
    log("Writing predictions to DB...")

    records = []
    for lid, metrics in league_metrics.items():
        mask      = (matches["league_id"] == lid).values
        idx       = np.where(mask)[0]
        split     = int(len(idx) * 0.8)
        eval_idx  = idx[split:]
        eval_matches = matches.iloc[eval_idx]

        for i, (_, row) in enumerate(eval_matches.iterrows()):
            global_i = eval_idx[i]
            probs    = all_probs[global_i]
            if probs.sum() == 0:
                continue
            records.append({
                "match_id":           int(row["id"]),
                "predicted_home_win": float(probs[0]),
                "predicted_draw":     float(probs[1]),
                "predicted_away_win": float(probs[2]),
                "confidence":         float(np.max(probs)),
                "prediction_type":    "match_winner",
                "created_at":         datetime.now(timezone.utc),
            })

    match_ids = [r["match_id"] for r in records]

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM predictions WHERE match_id = ANY(:ids)"),
            {"ids": match_ids}
        )

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

    log(f"Saved {len(records)} predictions")
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