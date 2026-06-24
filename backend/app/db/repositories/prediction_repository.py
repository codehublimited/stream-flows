from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
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
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid match_id: match does not exist.")
    db.refresh(db_prediction)
    return db_prediction


def _outcome_label(home_score, away_score):
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return "Home"
    elif home_score == away_score:
        return "Draw"
    else:
        return "Away"


def _predicted_label(home_prob, draw_prob, away_prob):
    if home_prob is None:
        return None
    probs = {"Home": home_prob, "Draw": draw_prob, "Away": away_prob}
    return max(probs, key=probs.get)


def get_rich_predictions(db: Session, skip: int = 0, limit: int = 50,
                         league_id: int = None, correct_only: bool = None):
    sql = text("""
        SELECT
            p.id            AS prediction_id,
            p.match_id,
            m.match_date,
            m.league_id,
            l.name          AS league_name,
            ht.name         AS home_team,
            at.name         AS away_team,
            m.home_score,
            m.away_score,
            p.predicted_home_win,
            p.predicted_draw,
            p.predicted_away_win,
            p.confidence,
            p.created_at
        FROM predictions p
        JOIN matches  m  ON m.id  = p.match_id
        JOIN teams    ht ON ht.id = m.home_team_id
        JOIN teams    at ON at.id = m.away_team_id
        JOIN leagues  l  ON l.id  = m.league_id
        WHERE (:league_id IS NULL OR m.league_id = :league_id)
        ORDER BY p.confidence DESC, m.match_date DESC
        LIMIT :limit OFFSET :skip
    """)

    rows = db.execute(sql, {
        "league_id": league_id,
        "limit": limit,
        "skip": skip,
    }).fetchall()

    results = []
    for row in rows:
        actual = _outcome_label(row.home_score, row.away_score)
        predicted = _predicted_label(
            row.predicted_home_win, row.predicted_draw, row.predicted_away_win
        )
        correct = (predicted == actual) if (predicted and actual) else None

        if correct_only is True and correct is not True:
            continue
        if correct_only is False and correct is not False:
            continue

        results.append({
            "prediction_id":      row.prediction_id,
            "match_id":           row.match_id,
            "match_date":         row.match_date,
            "league_id":          row.league_id,
            "league_name":        row.league_name,
            "home_team":          row.home_team,
            "away_team":          row.away_team,
            "home_score":         row.home_score,
            "away_score":         row.away_score,
            "predicted_home_win": row.predicted_home_win,
            "predicted_draw":     row.predicted_draw,
            "predicted_away_win": row.predicted_away_win,
            "confidence":         row.confidence,
            "predicted_outcome":  predicted,
            "actual_outcome":     actual,
            "correct":            correct,
            "created_at":         row.created_at,
        })

    return results


def get_prediction_stats(db: Session):
    sql = text("""
        WITH ranked AS (
            SELECT
                p.id,
                m.league_id,
                l.name AS league_name,
                m.home_score,
                m.away_score,
                p.predicted_home_win,
                p.predicted_draw,
                p.predicted_away_win,
                ROW_NUMBER() OVER (ORDER BY m.match_date) AS rn,
                COUNT(*) OVER () AS total_count
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            JOIN leagues l ON l.id = m.league_id
        ),
        eval_set AS (
            SELECT * FROM ranked
            WHERE rn > total_count * 0.8
        ),
        correct_flag AS (
            SELECT
                league_id,
                league_name,
                CASE
                    WHEN home_score > away_score
                         AND predicted_home_win >= predicted_draw
                         AND predicted_home_win >= predicted_away_win THEN 1
                    WHEN home_score = away_score
                         AND predicted_draw >= predicted_home_win
                         AND predicted_draw >= predicted_away_win THEN 1
                    WHEN home_score < away_score
                         AND predicted_away_win >= predicted_home_win
                         AND predicted_away_win >= predicted_draw THEN 1
                    ELSE 0
                END AS correct,
                CASE WHEN home_score > away_score
                     AND predicted_home_win >= predicted_draw
                     AND predicted_home_win >= predicted_away_win THEN 1 ELSE 0
                END AS home_correct,
                CASE WHEN home_score = away_score
                     AND predicted_draw >= predicted_home_win
                     AND predicted_draw >= predicted_away_win THEN 1 ELSE 0
                END AS draw_correct,
                CASE WHEN home_score < away_score
                     AND predicted_away_win >= predicted_home_win
                     AND predicted_away_win >= predicted_draw THEN 1 ELSE 0
                END AS away_correct
            FROM eval_set
        )
        SELECT
            league_id,
            league_name,
            COUNT(*)           AS total,
            SUM(correct)       AS correct,
            SUM(home_correct)  AS home_correct,
            SUM(draw_correct)  AS draw_correct,
            SUM(away_correct)  AS away_correct
        FROM correct_flag
        GROUP BY league_id, league_name
        ORDER BY correct DESC
    """)

    rows = db.execute(sql).fetchall()
    return [
        {
            "league_id":    row.league_id,
            "league_name":  row.league_name,
            "total":        row.total,
            "correct":      row.correct,
            "accuracy":     round(row.correct / row.total, 4) if row.total else 0.0,
            "home_correct": row.home_correct,
            "draw_correct": row.draw_correct,
            "away_correct": row.away_correct,
        }
        for row in rows
    ]