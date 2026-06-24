from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.team import TeamCreate, TeamOut
from app.services import team_service

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/", response_model=list[TeamOut])
def read_teams(db: Session = Depends(get_db)):
    return team_service.list_teams(db)


@router.get("/{team_id}", response_model=TeamOut)
def read_team(team_id: int, db: Session = Depends(get_db)):
    team = team_service.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.post("/", response_model=TeamOut)
def create_team(team: TeamCreate, db: Session = Depends(get_db)):
    return team_service.add_team(db, team)
