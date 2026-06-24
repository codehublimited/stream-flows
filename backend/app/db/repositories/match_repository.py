from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.match import Match
from app.schemas.match import MatchCreate


def get_all_matches(db: Session):
    return db.query(Match).all()


def get_match_by_id(db: Session, match_id: int):
    return db.query(Match).filter(Match.id == match_id).first()


def create_match(db: Session, match: MatchCreate):
    db_match = Match(**match.model_dump())
    db.add(db_match)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "foreign key" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="Invalid home_team_id, away_team_id, or league_id.")
        raise HTTPException(status_code=409, detail="A match with this api_id already exists.")
    db.refresh(db_match)
    return db_match
