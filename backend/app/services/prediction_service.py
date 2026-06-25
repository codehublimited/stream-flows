import joblib
import pandas as pd
from typing import Dict, Any
from app.db.session import get_db
from app.db.repositories.prediction_repository import create_prediction
from app.schemas.prediction import PredictionCreate

class PredictionService:
    def __init__(self):
        self.btts_model = joblib.load("app/ml/btts_model.joblib")
        self.over25_model = joblib.load("app/ml/over25_model.joblib")
        self.feature_columns = joblib.load("app/ml/btts_feature_columns.joblib")
   
    def predict(self, match_features: Dict[str, Any]) -> Dict[str, Any]:
        df = pd.DataFrame([match_features])
        X = df.copy()
        X = pd.get_dummies(X, columns=["league_id"], prefix="league")
        
        for col in self.feature_columns:
            if col not in X.columns:
                X[col] = 0
        X = X[self.feature_columns]
        
        btts_prob = self.btts_model.predict_proba(X)[0][1]
        over25_prob = self.over25_model.predict_proba(X)[0][1]
        
        result = {
            "btts_probability": round(float(btts_prob), 4),
            "over25_probability": round(float(over25_prob), 4),
            "recommended_bets": self._get_recommendations(btts_prob, over25_prob)
        }
        return result
   
    def _get_recommendations(self, btts_prob: float, over25_prob: float):
        rec = []
        if btts_prob > 0.60: rec.append("BTTS - Yes")
        if over25_prob > 0.58: rec.append("Over 2.5 Goals")
        return rec if rec else ["No strong recommendation"]

# Singleton
prediction_service = PredictionService()