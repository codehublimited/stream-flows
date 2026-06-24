from sqlalchemy.orm import Session
from app.db.repositories import prediction_repository
from app.schemas.prediction import PredictionCreate


def list_predictions(db: Session):
    return prediction_repository.get_all_predictions(db)


def get_prediction(db: Session, prediction_id: int):
    return prediction_repository.get_prediction_by_id(db, prediction_id)


def add_prediction(db: Session, prediction: PredictionCreate):
    return prediction_repository.create_prediction(db, prediction)


def list_rich_predictions(db: Session, skip: int = 0, limit: int = 50,
                          league_id: int = None, correct_only: bool = None):
    return prediction_repository.get_rich_predictions(db, skip, limit, league_id, correct_only)


def get_stats(db: Session):
    return prediction_repository.get_prediction_stats(db)