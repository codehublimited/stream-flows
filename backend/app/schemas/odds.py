from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OddsBase(BaseModel):
    match_id: int
    bookmaker: Optional[str] = None
    home_win: Optional[float] = None
    draw: Optional[float] = None
    away_win: Optional[float] = None
    timestamp: Optional[datetime] = None


class OddsCreate(OddsBase):
    pass


class OddsOut(OddsBase):
    id: int

    class Config:
        from_attributes = True
