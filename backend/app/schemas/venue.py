from pydantic import BaseModel
from typing import Optional


class VenueBase(BaseModel):
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    capacity: Optional[int] = None


class VenueCreate(VenueBase):
    pass


class VenueOut(VenueBase):
    id: int

    class Config:
        from_attributes = True
