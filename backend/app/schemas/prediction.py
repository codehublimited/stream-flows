from pydantic import BaseModel
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
