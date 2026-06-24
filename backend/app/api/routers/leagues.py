from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.league import LeagueCreate, LeagueOut
from app.services import league_service

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/", response_model=list[LeagueOut])
def read_leagues(db: Session = Depends(get_db)):
    return league_service.list_leagues(db)


@router.get("/{league_id}", response_model=LeagueOut)
def read_league(league_id: int, db: Session = Depends(get_db)):
    league = league_service.get_league(db, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league


@router.post("/", response_model=LeagueOut)
def create_league(league: LeagueCreate, db: Session = Depends(get_db)):
    return league_service.add_league(db, league)
