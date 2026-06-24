from pydantic import BaseModel
from typing import Optional


class TeamBase(BaseModel):
    name: str
    country: Optional[str] = None
    api_id: Optional[str] = None
    logo: Optional[str] = None
    league_id: Optional[int] = None


class TeamCreate(TeamBase):
    pass


class TeamOut(TeamBase):
    id: int

    class Config:
        from_attributes = True
