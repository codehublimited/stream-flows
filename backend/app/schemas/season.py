from pydantic import BaseModel
from typing import Optional
from datetime import date


class SeasonBase(BaseModel):
    league_id: int
    year: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[int] = 0


class SeasonCreate(SeasonBase):
    pass


class SeasonOut(SeasonBase):
    id: int

    class Config:
        from_attributes = True
