from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.season import Season
from app.schemas.season import SeasonCreate


def get_all_seasons(db: Session):
    return db.query(Season).all()


def get_season_by_id(db: Session, season_id: int):
    return db.query(Season).filter(Season.id == season_id).first()


def get_season_by_league_and_year(db: Session, league_id: int, year: int):
    return db.query(Season).filter(
        Season.league_id == league_id, Season.year == year
    ).first()


def create_season(db: Session, season: SeasonCreate):
    db_season = Season(**season.model_dump())
    db.add(db_season)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "foreign key" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="Invalid league_id: league does not exist.")
        raise HTTPException(status_code=409, detail="Season already exists.")
    db.refresh(db_season)
    return db_season
