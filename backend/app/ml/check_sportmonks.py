import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("SPORTMONKS_KEY")

print("Key loaded:", token[:10] + "..." if token else None)
print()

# Test 1: a free/basic endpoint to confirm the key works at all
print("--- Test 1: /football/leagues (basic auth check) ---")
resp = requests.get(
    "https://api.sportmonks.com/v3/football/leagues",
    params={"api_token": token}
)
print("HTTP status:", resp.status_code)
data = resp.json()
print("Message/error field:", data.get("message"))
print("Subscription field:", data.get("subscription"))
print("Number of leagues returned:", len(data.get("data", [])))
print()
print(json.dumps(data, indent=2)[:1500])
