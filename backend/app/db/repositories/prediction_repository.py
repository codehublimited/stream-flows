from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.prediction import Prediction
from app.schemas.prediction import PredictionCreate


def get_all_predictions(db: Session):
    return db.query(Prediction).all()


def get_prediction_by_id(db: Session, prediction_id: int):
    return db.query(Prediction).filter(Prediction.id == prediction_id).first()


def create_prediction(db: Session, prediction: PredictionCreate):
    db_prediction = Prediction(**prediction.model_dump())
    db.add(db_prediction)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid match_id: match does not exist.")
    db.refresh(db_prediction)
    return db_prediction
