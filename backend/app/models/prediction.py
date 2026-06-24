from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    
    predicted_home_win = Column(Float, nullable=True)
    predicted_draw = Column(Float, nullable=True)
    predicted_away_win = Column(Float, nullable=True)
    
    confidence = Column(Float, nullable=True)        # 0.0 to 1.0
    prediction_type = Column(String, default="match_winner")
    created_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match")
