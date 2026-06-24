from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionLocal

router = APIRouter()

@router.get("/db-health")
def db_health():

    db = SessionLocal()

    try:

        result = db.execute(
            text("SELECT version();")
        )

        version = result.scalar()

        return {
            "database": "connected",
            "postgres_version": version
        }

    except Exception as e:

        return {
            "database": "failed",
            "error": str(e)
        }

    finally:
        db.close()