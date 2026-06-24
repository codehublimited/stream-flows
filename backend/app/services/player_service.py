from sqlalchemy.orm import Session
from app.db.repositories import player_repository
from app.schemas.player import PlayerCreate


def list_players(db: Session):
    return player_repository.get_all_players(db)


def get_player(db: Session, player_id: int):
    return player_repository.get_player_by_id(db, player_id)


def add_player(db: Session, player: PlayerCreate):
    return player_repository.create_player(db, player)
