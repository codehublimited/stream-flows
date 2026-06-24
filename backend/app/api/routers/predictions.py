from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.prediction import PredictionCreate, PredictionOut
from app.services import prediction_service
from app.models.match import Match
from app.ml.prediction_service import predict_match

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


@router.post("/generate/{match_id}", response_model=PredictionOut)
def generate_prediction(match_id: int, db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    try:
        result = predict_match(db, match)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Prediction model not found. Run training first."
        )

    prediction_data = PredictionCreate(
        match_id=match.id,
        predicted_home_win=result["predicted_home_win"],
        predicted_draw=result["predicted_draw"],
        predicted_away_win=result["predicted_away_win"],
        confidence=result["confidence"],
        prediction_type="match_winner",
    )
    return prediction_service.add_prediction(db, prediction_data)
