from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.player import PlayerCreate, PlayerOut
from app.services import player_service

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/", response_model=list[PlayerOut])
def read_players(db: Session = Depends(get_db)):
    return player_service.list_players(db)


@router.get("/{player_id}", response_model=PlayerOut)
def read_player(player_id: int, db: Session = Depends(get_db)):
    player = player_service.get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.post("/", response_model=PlayerOut)
def create_player(player: PlayerCreate, db: Session = Depends(get_db)):
    return player_service.add_player(db, player)
