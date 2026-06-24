import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime
import logging
import warnings
warnings.filterwarnings('ignore')

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'sports_db',
    'user': 'postgres',
    'password': '$plainPassword'
}
DB_DRIVER = 'postgresql'

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
engine = create_engine(f"{DB_DRIVER}://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

# ---------- LOAD TABLES ----------
logger.info("Loading tables...")
matches = pd.read_sql("SELECT * FROM matches ORDER BY match_date", engine)
team_form = pd.read_sql("SELECT * FROM team_form", engine)
h2h = pd.read_sql("SELECT * FROM h2h", engine)
league_context = pd.read_sql("SELECT * FROM league_context", engine)

# ---------- PREPARE TARGET ----------
def encode_result(row):
    if row['status'] != 'FT':
        return np.nan
    return 0 if row['score_home'] > row['score_away'] else (1 if row['score_home'] == row['score_away'] else 2)

matches['target'] = matches.apply(encode_result, axis=1)
train_df = matches[matches['target'].notna()].copy()
pred_df = matches[matches['target'].isna()].copy()
logger.info(f"Train: {len(train_df)}, Predict: {len(pred_df)}")
if len(pred_df) == 0:
    logger.warning("No upcoming matches. Exiting.")
    exit(0)

# ---------- FEATURE ENGINEERING ----------
def get_features(row, team_form, h2h, league_context):
    home = row['home_team_id']
    away = row['away_team_id']
    league = row['league_id']
    cutoff = row['match_date'] if row['match_date'] < datetime.now().date() else datetime.now().date()
    f = {}

    lc = league_context[league_context['league_id'] == league]
    f['league_avg_goals'] = lc['avg_goals'].iloc[0] if not lc.empty else 0
    f['league_over25_pct'] = lc['over25_percent'].iloc[0] if not lc.empty else 0

    hf = team_form[(team_form['team_id'] == home) & (team_form['as_of_date'] <= cutoff)]
    if not hf.empty:
        h = hf.iloc[0]
        f['home_form_points'] = h['form_points']
        f['home_goals_scored'] = h['goals_scored']
        f['home_goals_conceded'] = h['goals_conceded']
        f['home_xg_avg'] = h['xg_avg']
        f['home_shots'] = h['shots']
        f['home_corners'] = h['corners']
    else:
        f['home_form_points'] = 0
        f['home_goals_scored'] = 0
        f['home_goals_conceded'] = 0
        f['home_xg_avg'] = 0
        f['home_shots'] = 0
        f['home_corners'] = 0

    af = team_form[(team_form['team_id'] == away) & (team_form['as_of_date'] <= cutoff)]
    if not af.empty:
        a = af.iloc[0]
        f['away_form_points'] = a['form_points']
        f['away_goals_scored'] = a['goals_scored']
        f['away_goals_conceded'] = a['goals_conceded']
        f['away_xg_avg'] = a['xg_avg']
        f['away_shots'] = a['shots']
        f['away_corners'] = a['corners']
    else:
        f['away_form_points'] = 0
        f['away_goals_scored'] = 0
        f['away_goals_conceded'] = 0
        f['away_xg_avg'] = 0
        f['away_shots'] = 0
        f['away_corners'] = 0

    hh = h2h[(h2h['home_team_id'] == home) & (h2h['away_team_id'] == away)]
    if not hh.empty:
        h = hh.iloc[0]
        f['h2h_home_wins'] = h['home_wins']
        f['h2h_draws'] = h['draws']
        f['h2h_away_wins'] = h['away_wins']
        f['h2h_avg_goals'] = h['avg_goals']
        f['h2h_over25_pct'] = h['over25_percent']
    else:
        f['h2h_home_wins'] = 0
        f['h2h_draws'] = 0
        f['h2h_away_wins'] = 0
        f['h2h_avg_goals'] = 0
        f['h2h_over25_pct'] = 0

    f['form_diff_points'] = f['home_form_points'] - f['away_form_points']
    f['form_diff_goals'] = (f['home_goals_scored'] - f['home_goals_conceded']) - (f['away_goals_scored'] - f['away_goals_conceded'])
    f['goal_ratio'] = (f['home_goals_scored'] + 1) / (f['home_goals_scored'] + f['away_goals_scored'] + 2)
    f['xg_diff'] = f['home_xg_avg'] - f['away_xg_avg']
    f['shots_diff'] = f['home_shots'] - f['away_shots']
    f['corners_diff'] = f['home_corners'] - f['away_corners']
    return f

logger.info("Engineering features...")
train_feats = [get_features(row, team_form, h2h, league_context) for _, row in train_df.iterrows()]
pred_feats = [get_features(row, team_form, h2h, league_context) for _, row in pred_df.iterrows()]
X_train = pd.DataFrame(train_feats)
X_pred = pd.DataFrame(pred_feats)

from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_pred_scaled = scaler.transform(X_pred)

y_outcome = train_df['target'].astype(int)
y_home_xg = train_df['score_home'].fillna(0).values
y_away_xg = train_df['score_away'].fillna(0).values

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, VotingClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier, XGBRegressor

logger.info("Training models...")
rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
xgb = XGBClassifier(n_estimators=100, random_state=42, use_label_encoder=False, eval_metric='mlogloss')
lr = LogisticRegression(max_iter=1000, random_state=42)

rf.fit(X_train_scaled, y_outcome)
xgb.fit(X_train_scaled, y_outcome)
lr.fit(X_train_scaled, y_outcome)

voting = VotingClassifier(estimators=[('rf',rf),('xgb',xgb),('lr',lr)], voting='soft')
voting.fit(X_train_scaled, y_outcome)

rf_xg_home = RandomForestRegressor(n_estimators=100, random_state=42)
xgb_xg_home = XGBRegressor(n_estimators=100, random_state=42)
rf_xg_home.fit(X_train_scaled, y_home_xg)
xgb_xg_home.fit(X_train_scaled, y_home_xg)

rf_xg_away = RandomForestRegressor(n_estimators=100, random_state=42)
xgb_xg_away = XGBRegressor(n_estimators=100, random_state=42)
rf_xg_away.fit(X_train_scaled, y_away_xg)
xgb_xg_away.fit(X_train_scaled, y_away_xg)

def avg_pred(r1, r2, X): return (r1.predict(X) + r2.predict(X)) / 2

probs = voting.predict_proba(X_pred_scaled)
probs_rf = rf.predict_proba(X_pred_scaled)
probs_xgb = xgb.predict_proba(X_pred_scaled)
probs_lr = lr.predict_proba(X_pred_scaled)
agreement = [np.mean(np.std([probs_rf[i], probs_xgb[i], probs_lr[i]], axis=0)) for i in range(len(X_pred_scaled))]
confidence = np.max(probs, axis=1)
home_xg = avg_pred(rf_xg_home, xgb_xg_home, X_pred_scaled)
away_xg = avg_pred(rf_xg_away, xgb_xg_away, X_pred_scaled)

with engine.connect() as conn:
    conn.execute(text("DELETE FROM predictions WHERE match_id = ANY(:ids)"), {"ids": pred_df['match_id'].tolist()})
    conn.commit()

out = pd.DataFrame({
    'match_id': pred_df['match_id'].values,
    'home_win_prob': probs[:,0],
    'draw_prob': probs[:,1],
    'away_win_prob': probs[:,2],
    'predicted_home_xg': home_xg,
    'predicted_away_xg': away_xg,
    'confidence_score': confidence,
    'model_agreement': agreement,
    'model_name': 'voting_ensemble_no_stats',
    'model_version': '1.2',
    'prediction_date': datetime.now()
})
out.to_sql('predictions', engine, if_exists='append', index=False, method='multi')
logger.info(f"Saved {len(out)} predictions.")
logger.info("All done.")
