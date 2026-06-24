import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()
headers = {"x-apisports-key": os.getenv("API_FOOTBALL_KEY")}

fixture_ids = [1208021, 1208036, 1208059, 1208076, 1208091, 1208119,
               1213754, 1213747, 1213752, 1213751]

for fid in fixture_ids:
    resp = requests.get(
        "https://v3.football.api-sports.io/odds",
        headers=headers,
        params={"fixture": fid}
    )
    data = resp.json()
    results = data.get("results")
    errors = data.get("errors")
    response = data.get("response", [])

    print(f"fixture={fid}  results={results}  errors={errors}")
    if response:
        bookmakers = response[0].get("bookmakers", [])
        print(f"  -> {len(bookmakers)} bookmakers returned")
        if bookmakers:
            print(f"  -> sample bet names: {[b['name'] for b in bookmakers[0].get('bets', [])][:5]}")
    print()
    time.sleep(7)
