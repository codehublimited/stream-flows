from sqlalchemy.orm import Session
from app.db.repositories import venue_repository
from app.schemas.venue import VenueCreate


def list_venues(db: Session):
    return venue_repository.get_all_venues(db)


def get_venue(db: Session, venue_id: int):
    return venue_repository.get_venue_by_id(db, venue_id)


def add_venue(db: Session, venue: VenueCreate):
    return venue_repository.create_venue(db, venue)
