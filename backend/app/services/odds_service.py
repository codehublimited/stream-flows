from sqlalchemy.orm import Session
from app.db.repositories import odds_repository
from app.schemas.odds import OddsCreate


def list_odds(db: Session):
    return odds_repository.get_all_odds(db)


def get_odds(db: Session, odds_id: int):
    return odds_repository.get_odds_by_id(db, odds_id)


def add_odds(db: Session, odds: OddsCreate):
    return odds_repository.create_odds(db, odds)
