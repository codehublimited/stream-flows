from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.odds import Odds
from app.schemas.odds import OddsCreate


def get_all_odds(db: Session):
    return db.query(Odds).all()


def get_odds_by_id(db: Session, odds_id: int):
    return db.query(Odds).filter(Odds.id == odds_id).first()


def create_odds(db: Session, odds: OddsCreate):
    db_odds = Odds(**odds.model_dump())
    db.add(db_odds)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid match_id: match does not exist.")
    db.refresh(db_odds)
    return db_odds
