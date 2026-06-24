from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.venue import VenueCreate, VenueOut
from app.services import venue_service

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("/", response_model=list[VenueOut])
def read_venues(db: Session = Depends(get_db)):
    return venue_service.list_venues(db)


@router.get("/{venue_id}", response_model=VenueOut)
def read_venue(venue_id: int, db: Session = Depends(get_db)):
    venue = venue_service.get_venue(db, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@router.post("/", response_model=VenueOut)
def create_venue(venue: VenueCreate, db: Session = Depends(get_db)):
    return venue_service.add_venue(db, venue)
