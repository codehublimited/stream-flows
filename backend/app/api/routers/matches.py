from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.match import MatchCreate, MatchOut
from app.services import match_service

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/", response_model=list[MatchOut])
def read_matches(db: Session = Depends(get_db)):
    return match_service.list_matches(db)


@router.get("/{match_id}", response_model=MatchOut)
def read_match(match_id: int, db: Session = Depends(get_db)):
    match = match_service.get_match(db, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.post("/", response_model=MatchOut)
def create_match(match: MatchCreate, db: Session = Depends(get_db)):
    return match_service.add_match(db, match)
