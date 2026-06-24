from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.player import Player
from app.schemas.player import PlayerCreate


def get_all_players(db: Session):
    return db.query(Player).all()


def get_player_by_id(db: Session, player_id: int):
    return db.query(Player).filter(Player.id == player_id).first()


def create_player(db: Session, player: PlayerCreate):
    db_player = Player(**player.model_dump())
    db.add(db_player)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "foreign key" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="Invalid team_id: team does not exist.")
        raise HTTPException(status_code=409, detail="A player with this api_id already exists.")
    db.refresh(db_player)
    return db_player
