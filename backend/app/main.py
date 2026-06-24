from fastapi import FastAPI
from app.db.session import init_db
from app.api.routers import leagues, teams, venues, players, matches, odds, predictions, seasons

app = FastAPI()

app.include_router(leagues.router)
app.include_router(teams.router)
app.include_router(venues.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(odds.router)
app.include_router(predictions.router)
app.include_router(seasons.router)


@app.on_event("startup")
def startup():
    try:
        init_db()
    except Exception as e:
        print("DB INIT ERROR:", e)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-test")
def db_test():
    return {"db": "connected"}
