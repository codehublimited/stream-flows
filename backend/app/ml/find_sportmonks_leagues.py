import os
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("SPORTMONKS_KEY")

league_names = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]

for name in league_names:
    resp = requests.get(
        f"https://api.sportmonks.com/v3/football/leagues/search/{name}",
        params={"api_token": token}
    )
    print(f"--- Search: {name} ---  HTTP {resp.status_code}")
    data = resp.json()
    if "message" in data:
        print(f"  Error: {data['message']}")
    results = data.get("data", [])
    for r in results[:5]:
        print(f"  id={r['id']}  name={r['name']}  country_id={r.get('country_id')}")
    print()
