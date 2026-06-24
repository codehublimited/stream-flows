from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.venue import Venue
from app.schemas.venue import VenueCreate


def get_all_venues(db: Session):
    return db.query(Venue).all()


def get_venue_by_id(db: Session, venue_id: int):
    return db.query(Venue).filter(Venue.id == venue_id).first()


def create_venue(db: Session, venue: VenueCreate):
    db_venue = Venue(**venue.model_dump())
    db.add(db_venue)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Venue already exists.")
    db.refresh(db_venue)
    return db_venue
