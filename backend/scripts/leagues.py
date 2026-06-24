from pydantic import BaseModel
from typing import Optional

class LeagueBase(BaseModel):
    name: str
    country: Optional[str] = None
    logo: Optional[str] = None

class LeagueCreate(LeagueBase):
    api_id: Optional[str] = None

class LeagueResponse(LeagueBase):
    id: int
    api_id: Optional[str] = None

    class Config:
        from_attributes = True
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.league import League
from app.schemas.league import LeagueResponse, LeagueCreate

router = APIRouter(prefix="/leagues", tags=["leagues"])

@router.get("/", response_model=list[LeagueResponse])
def get_all_leagues(db: Session = Depends(get_db)):
    """Get all leagues"""
    return db.query(League).all()

@router.post("/", response_model=LeagueResponse)
def create_league(league_in: LeagueCreate, db: Session = Depends(get_db)):
    """Create new league"""
    league = League(**league_in.dict())
    db.add(league)
    db.commit()
    db.refresh(league)
    return league