from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.season import SeasonCreate, SeasonOut
from app.services import season_service

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("/", response_model=list[SeasonOut])
def read_seasons(db: Session = Depends(get_db)):
    return season_service.list_seasons(db)


@router.get("/{season_id}", response_model=SeasonOut)
def read_season(season_id: int, db: Session = Depends(get_db)):
    season = season_service.get_season(db, season_id)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")
    return season


@router.post("/", response_model=SeasonOut)
def create_season(season: SeasonCreate, db: Session = Depends(get_db)):
    return season_service.add_season(db, season)
