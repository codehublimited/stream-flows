from sqlalchemy.orm import Session
from app.db.repositories import league_repository
from app.schemas.league import LeagueCreate


def list_leagues(db: Session):
    return league_repository.get_all_leagues(db)


def get_league(db: Session, league_id: int):
    return league_repository.get_league_by_id(db, league_id)


def add_league(db: Session, league: LeagueCreate):
    return league_repository.create_league(db, league)
