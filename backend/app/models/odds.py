from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime


class Odds(Base):
    __tablename__ = "odds"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    bookmaker = Column(String, nullable=True)

    home_win = Column(Float, nullable=True)
    draw = Column(Float, nullable=True)
    away_win = Column(Float, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match")
