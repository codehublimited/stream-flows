from pydantic import BaseModel
from typing import Optional


class LeagueBase(BaseModel):
    name: str
    country: Optional[str] = None
    api_id: Optional[str] = None
    logo: Optional[str] = None


class LeagueCreate(LeagueBase):
    pass


class LeagueOut(LeagueBase):
    id: int

    class Config:
        from_attributes = True
