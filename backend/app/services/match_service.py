from sqlalchemy.orm import Session
from app.db.repositories import match_repository
from app.schemas.match import MatchCreate


def list_matches(db: Session):
    return match_repository.get_all_matches(db)


def get_match(db: Session, match_id: int):
    return match_repository.get_match_by_id(db, match_id)


def add_match(db: Session, match: MatchCreate):
    return match_repository.create_match(db, match)
