from sqlalchemy.orm import Session
from app.db.repositories import season_repository
from app.schemas.season import SeasonCreate


def list_seasons(db: Session):
    return season_repository.get_all_seasons(db)


def get_season(db: Session, season_id: int):
    return season_repository.get_season_by_id(db, season_id)


def add_season(db: Session, season: SeasonCreate):
    return season_repository.create_season(db, season)
