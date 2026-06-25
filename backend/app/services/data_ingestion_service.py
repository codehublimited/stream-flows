import requests
import time
import os
from typing import Dict, List
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.league import League

class DataIngestionService:
    def __init__(self):
        self.api_key = os.getenv("API_FOOTBALL_KEY")
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": self.api_key} if self.api_key else {}

    def safe_request(self, endpoint: str, params: dict = None) -> Dict:
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.get(url, headers=self.headers, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"? API Request failed {endpoint}: {e}")
            return None

    def ingest_leagues(self):
        db: Session = next(get_db())
        try:
            print("?? Fetching leagues from API-Football...")
            data = self.safe_request("/leagues")
            if not data or "response" not in data:
                print("?? Using sample leagues")
                leagues_data = [
                    {"id": 39, "name": "Premier League", "country": "England", "logo": None},
                    {"id": 140, "name": "La Liga", "country": "Spain", "logo": None},
                ]
            else:
                leagues_data = [item["league"] for item in data["response"]]

            added = 0
            updated = 0
            for league in leagues_data[:120]:
                api_id = str(league["id"])
                country_name = None
                if isinstance(league.get("country"), dict):
                    country_name = league["country"].get("name")
                else:
                    country_name = league.get("country")

                existing = db.query(League).filter(League.api_id == api_id).first()
                if existing:
                    existing.name = league["name"]
                    existing.country = country_name
                    existing.logo = league.get("logo")
                    updated += 1
                else:
                    db.add(League(
                        name=league["name"],
                        country=country_name,
                        api_id=api_id,
                        logo=league.get("logo")
                    ))
                    added += 1
                db.commit()

            print(f"? Leagues done: {added} added, {updated} updated")
        except Exception as e:
            print(f"? League ingestion error: {e}")
            db.rollback()

    def run_daily_ingestion(self):
        print("?? Starting Daily Data Ingestion...")
        start = time.time()
        self.ingest_leagues()
        print(f"? Ingestion completed in {time.time() - start:.1f} seconds")

ingestion_service = DataIngestionService()
