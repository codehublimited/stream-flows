from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.odds import OddsCreate, OddsOut
from app.services import odds_service

router = APIRouter(prefix="/odds", tags=["odds"])


@router.get("/", response_model=list[OddsOut])
def read_odds(db: Session = Depends(get_db)):
    return odds_service.list_odds(db)


@router.get("/{odds_id}", response_model=OddsOut)
def read_odds_by_id(odds_id: int, db: Session = Depends(get_db)):
    odds = odds_service.get_odds(db, odds_id)
    if not odds:
        raise HTTPException(status_code=404, detail="Odds not found")
    return odds


@router.post("/", response_model=OddsOut)
def create_odds(odds: OddsCreate, db: Session = Depends(get_db)):
    return odds_service.add_odds(db, odds)
