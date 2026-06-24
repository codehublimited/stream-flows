from pydantic import BaseModel
from typing import Optional


class PlayerBase(BaseModel):
    name: str
    api_id: Optional[str] = None
    position: Optional[str] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    team_id: Optional[int] = None


class PlayerCreate(PlayerBase):
    pass


class PlayerOut(PlayerBase):
    id: int

    class Config:
        from_attributes = True
