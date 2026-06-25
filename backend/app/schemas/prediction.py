from pydantic import BaseModel, computed_field
from typing import Optional
from datetime import datetime


class PredictionBase(BaseModel):
    match_id: int
    predicted_home_win: Optional[float] = None
    predicted_draw: Optional[float] = None
    predicted_away_win: Optional[float] = None
    confidence: Optional[float] = None
    prediction_type: Optional[str] = "match_winner"
    created_at: Optional[datetime] = None


class PredictionCreate(PredictionBase):
    pass


class PredictionOut(PredictionBase):
    id: int

    class Config:
        from_attributes = True


class PredictionRich(BaseModel):
    """Prediction with full match context — used by the enriched endpoints."""
    prediction_id: int
    match_id: int
    match_date: Optional[datetime]
    league_id: Optional[int]
    league_name: Optional[str]
    home_team: Optional[str]
    away_team: Optional[str]
    home_score: Optional[int]
    away_score: Optional[int]
    predicted_home_win: Optional[float]
    predicted_draw: Optional[float]
    predicted_away_win: Optional[float]
    confidence: Optional[float]
    predicted_outcome: Optional[str]   # "Home", "Draw", "Away"
    actual_outcome: Optional[str]      # "Home", "Draw", "Away"
    correct: Optional[bool]            # None if no result yet
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class PredictionStats(BaseModel):
    league_id: Optional[int]
    league_name: Optional[str]
    total: int
    correct: int
    accuracy: float
    home_correct: int
    draw_correct: int
    away_correct: int

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class PredictionBase(BaseModel):
    match_id: int
    predicted_home_win: Optional[float] = None
    predicted_draw: Optional[float] = None
    predicted_away_win: Optional[float] = None
    btts_probability: Optional[float] = None
    over25_probability: Optional[float] = None
    confidence: Optional[float] = None

class PredictionCreate(PredictionBase):
    pass

class PredictionResponse(PredictionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True