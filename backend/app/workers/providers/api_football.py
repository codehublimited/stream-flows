import time
import os
from app.workers.http_client import safe_get

BASE_URL = "https://v3.football.api-sports.io"
REQUEST_DELAY_SECONDS = 7  # stay safely under per-minute rate limits

TOP_5_LEAGUE_IDS = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
}


def _headers():
    key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        print("WARNING: API_FOOTBALL_KEY not set, skipping API-Football.")
        return None
    return {"x-apisports-key": key}


def fetch_leagues():
    headers = _headers()
    if not headers:
        return []

    results = []
    for name, league_id in TOP_5_LEAGUE_IDS.items():
        data = safe_get(f"{BASE_URL}/leagues", headers=headers, params={"id": league_id})
        time.sleep(REQUEST_DELAY_SECONDS)
        if not data or not data.get("response"):
            continue
        entry = data["response"][0]
        league_info = entry["league"]
        country_info = entry["country"]
        results.append({
            "name": league_info["name"],
            "country": country_info.get("name"),
            "api_id": str(league_info["id"]),
            "logo": league_info.get("logo"),
        })
    return results


def fetch_teams(league_api_id: str, season: int = 2024):
    headers = _headers()
    if not headers:
        return []

    data = safe_get(f"{BASE_URL}/teams", headers=headers, params={"league": league_api_id, "season": season})
    time.sleep(REQUEST_DELAY_SECONDS)
    if not data or not data.get("response"):
        return []

    results = []
    for entry in data["response"]:
        team_info = entry["team"]
        results.append({
            "name": team_info["name"],
            "country": team_info.get("country"),
            "api_id": str(team_info["id"]),
            "logo": team_info.get("logo"),
        })
    return results


def fetch_fixtures(league_api_id: str, season: int = 2024):
    headers = _headers()
    if not headers:
        return []

    data = safe_get(f"{BASE_URL}/fixtures", headers=headers, params={"league": league_api_id, "season": season})
    time.sleep(REQUEST_DELAY_SECONDS)
    if not data or not data.get("response"):
        return []

    results = []
    for entry in data["response"]:
        fixture = entry["fixture"]
        teams = entry["teams"]
        goals = entry["goals"]
        results.append({
            "api_id": str(fixture["id"]),
            "home_team_api_id": str(teams["home"]["id"]),
            "away_team_api_id": str(teams["away"]["id"]),
            "league_api_id": league_api_id,
            "match_date": fixture.get("date"),
            "status": fixture["status"].get("short", "scheduled"),
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
        })
    return results
