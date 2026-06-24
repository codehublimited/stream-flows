from app.db.session import SessionLocal

# Import all models so SQLAlchemy's relationship resolver can see every class,
# even ones not directly queried by this script (e.g. Team -> Player).
from app.models import league, team, player, venue, match, odds, prediction  # noqa: F401

from app.db.repositories import league_repository, team_repository, match_repository
from app.schemas.league import LeagueCreate
from app.schemas.team import TeamCreate
from app.schemas.match import MatchCreate
from app.workers.providers import api_football
from fastapi import HTTPException
from datetime import datetime


def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def ingest_leagues(db):
    print("\n--- Ingesting leagues from API-Football ---")
    leagues = api_football.fetch_leagues()
    saved = 0
    for league_data in leagues:
        existing = db.query(league_repository.League).filter(
            league_repository.League.api_id == league_data["api_id"]
        ).first()
        if existing:
            print(f"SKIP (exists): {league_data['name']}")
            continue
        try:
            league_repository.create_league(db, LeagueCreate(**league_data))
            print(f"SAVED: {league_data['name']}")
            saved += 1
        except HTTPException as e:
            print(f"SKIP ({e.detail}): {league_data['name']}")
    print(f"Leagues ingested: {saved}")


def ingest_teams(db):
    print("\n--- Ingesting teams from API-Football ---")
    saved = 0
    for league_name, league_id in api_football.TOP_5_LEAGUE_IDS.items():
        league_obj = db.query(league_repository.League).filter(
            league_repository.League.api_id == str(league_id)
        ).first()
        if not league_obj:
            print(f"SKIP teams for {league_name}: league not in DB yet")
            continue

        teams = api_football.fetch_teams(str(league_id))
        for team_data in teams:
            existing = db.query(team_repository.Team).filter(
                team_repository.Team.api_id == team_data["api_id"]
            ).first()
            if existing:
                continue
            team_data["league_id"] = league_obj.id
            try:
                team_repository.create_team(db, TeamCreate(**team_data))
                saved += 1
            except HTTPException as e:
                print(f"SKIP ({e.detail}): {team_data['name']}")
    print(f"Teams ingested: {saved}")


def ingest_matches(db):
    print("\n--- Ingesting matches from API-Football ---")
    saved = 0
    for league_name, league_id in api_football.TOP_5_LEAGUE_IDS.items():
        league_obj = db.query(league_repository.League).filter(
            league_repository.League.api_id == str(league_id)
        ).first()
        if not league_obj:
            continue

        fixtures = api_football.fetch_fixtures(str(league_id))
        for fixture_data in fixtures:
            existing = db.query(match_repository.Match).filter(
                match_repository.Match.api_id == fixture_data["api_id"]
            ).first()
            if existing:
                continue

            home_team = db.query(team_repository.Team).filter(
                team_repository.Team.api_id == fixture_data["home_team_api_id"]
            ).first()
            away_team = db.query(team_repository.Team).filter(
                team_repository.Team.api_id == fixture_data["away_team_api_id"]
            ).first()
            if not home_team or not away_team:
                continue

            match_payload = {
                "api_id": fixture_data["api_id"],
                "home_team_id": home_team.id,
                "away_team_id": away_team.id,
                "league_id": league_obj.id,
                "match_date": parse_date(fixture_data["match_date"]),
                "status": fixture_data["status"],
                "home_score": fixture_data["home_score"],
                "away_score": fixture_data["away_score"],
            }
            try:
                match_repository.create_match(db, MatchCreate(**match_payload))
                saved += 1
            except HTTPException as e:
                print(f"SKIP match: {e.detail}")
    print(f"Matches ingested: {saved}")


def run_full_ingestion():
    db = SessionLocal()
    try:
        ingest_leagues(db)
        ingest_teams(db)
        ingest_matches(db)
    finally:
        db.close()
    print("\n=== Ingestion complete ===")


if __name__ == "__main__":
    run_full_ingestion()
