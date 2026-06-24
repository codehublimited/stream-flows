from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.team import Team
from app.schemas.team import TeamCreate


def get_all_teams(db: Session):
    return db.query(Team).all()


def get_team_by_id(db: Session, team_id: int):
    return db.query(Team).filter(Team.id == team_id).first()


def create_team(db: Session, team: TeamCreate):
    db_team = Team(**team.model_dump())
    db.add(db_team)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "foreign key" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="Invalid league_id: league does not exist.")
        raise HTTPException(status_code=409, detail="A team with this api_id already exists.")
    db.refresh(db_team)
    return db_team
