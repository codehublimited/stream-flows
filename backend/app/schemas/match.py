from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MatchBase(BaseModel):
    api_id: Optional[str] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    league_id: Optional[int] = None
    match_date: Optional[datetime] = None
    status: Optional[str] = "scheduled"
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class MatchCreate(MatchBase):
    pass


class MatchOut(MatchBase):
    id: int

    class Config:
        from_attributes = True
