from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.prediction import PredictionCreate, PredictionOut
from app.services import prediction_service

router = APIRouter(prefix="/predictions", tags=["predictions"])


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
