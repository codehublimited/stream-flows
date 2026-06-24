from sqlalchemy.orm import Session
from app.db.repositories import team_repository
from app.schemas.team import TeamCreate


def list_teams(db: Session):
    return team_repository.get_all_teams(db)


def get_team(db: Session, team_id: int):
    return team_repository.get_team_by_id(db, team_id)


def add_team(db: Session, team: TeamCreate):
    return team_repository.create_team(db, team)
