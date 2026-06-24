from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.league import League
from app.schemas.league import LeagueCreate


def get_all_leagues(db: Session):
    return db.query(League).all()


def get_league_by_id(db: Session, league_id: int):
    return db.query(League).filter(League.id == league_id).first()


def create_league(db: Session, league: LeagueCreate):
    db_league = League(**league.model_dump())
    db.add(db_league)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A league named '{league.name}' already exists."
        )
    db.refresh(db_league)
    return db_league
