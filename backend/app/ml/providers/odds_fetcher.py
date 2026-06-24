import os
import time
from app.workers.http_client import safe_get

BASE_URL = "https://v3.football.api-sports.io"
REQUEST_DELAY_SECONDS = 7


def _headers():
    key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        print("WARNING: API_FOOTBALL_KEY not set, skipping odds fetch.")
        return None
    return {"x-apisports-key": key}


def fetch_odds_for_fixture(fixture_api_id: str):
    headers = _headers()
    if not headers:
        return None

    data = safe_get(f"{BASE_URL}/odds", headers=headers, params={"fixture": fixture_api_id})
    time.sleep(REQUEST_DELAY_SECONDS)

    if not data or not data.get("response"):
        return None

    try:
        bookmakers = data["response"][0]["bookmakers"]
        if not bookmakers:
            return None
        bookmaker = bookmakers[0]
        bets = bookmaker.get("bets", [])
        match_winner_bet = next((b for b in bets if b["name"] == "Match Winner"), None)
        if not match_winner_bet:
            return None

        values = {v["value"]: float(v["odd"]) for v in match_winner_bet["values"]}
        return {
            "bookmaker": bookmaker.get("name"),
            "home_win": values.get("Home"),
            "draw": values.get("Draw"),
            "away_win": values.get("Away"),
        }
    except (KeyError, IndexError, ValueError, TypeError) as e:
        print(f"  Could not parse odds for fixture {fixture_api_id}: {e}")
        return None
