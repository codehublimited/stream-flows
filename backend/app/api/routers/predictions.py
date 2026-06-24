from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.deps import get_db
from app.schemas.prediction import PredictionCreate, PredictionOut, PredictionRich, PredictionStats
from app.services import prediction_service

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/stats", response_model=list[PredictionStats])
def prediction_stats(db: Session = Depends(get_db)):
    """Accuracy breakdown by league."""
    return prediction_service.get_stats(db)


@router.get("/rich", response_model=list[PredictionRich])
def rich_predictions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    league_id: Optional[int] = Query(None),
    correct: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """Predictions enriched with team names, scores, and correct/wrong flag."""
    return prediction_service.list_rich_predictions(db, skip, limit, league_id, correct)


@router.get("/", response_model=list[PredictionOut])
def read_predictions(db: Session = Depends(get_db)):
    return prediction_service.list_predictions(db)


@router.get("/{prediction_id}", response_model=PredictionOut)
def read_prediction(prediction_id: int, db: Session = Depends(get_db)):
    prediction = prediction_service.get_prediction(db, prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return prediction


@router.post("/", response_model=PredictionOut)
def create_prediction(prediction: PredictionCreate, db: Session = Depends(get_db)):
    return prediction_service.add_prediction(db, prediction)