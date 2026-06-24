from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    api_id = Column(String, unique=True, index=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    league_id = Column(Integer, ForeignKey("leagues.id"))
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True)

    match_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="scheduled")
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)

    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    league = relationship("League")
    season = relationship("Season", back_populates="matches")
