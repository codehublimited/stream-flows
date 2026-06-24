import os
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("API_FOOTBALL_KEY")

print("="*60)
print("API-FOOTBALL KEY DIAGNOSTIC")
print("="*60)
print(f"Key loaded: {key}")
print(f"Key length: {len(key) if key else 0}")
print()

# Test 1: /status endpoint - shows quota/subscription info if key is valid
print("--- Test 1: /status (account info) ---")
resp = requests.get(
    "https://v3.football.api-sports.io/status",
    headers={"x-apisports-key": key}
)
print("HTTP status code:", resp.status_code)
data = resp.json()
print("API errors field:", data.get("errors"))
print("API response field:", data.get("response"))
print()

# Test 2: /timezone endpoint - a totally free, no-quota-cost endpoint
# If THIS also fails with "missing key", the key itself is the problem,
# not quota exhaustion (since this endpoint doesn't cost quota).
print("--- Test 2: /timezone (free, no quota cost) ---")
resp2 = requests.get(
    "https://v3.football.api-sports.io/timezone",
    headers={"x-apisports-key": key}
)
print("HTTP status code:", resp2.status_code)
data2 = resp2.json()
print("API errors field:", data2.get("errors"))
print("Results count:", data2.get("results"))
print()

# Test 3: check response headers for rate limit info
print("--- Test 3: rate limit headers from last response ---")
for header_name in ["x-ratelimit-requests-limit", "x-ratelimit-requests-remaining",
                      "X-RateLimit-Limit", "X-RateLimit-Remaining"]:
    if header_name in resp2.headers:
        print(f"{header_name}: {resp2.headers[header_name]}")
print("All response headers:", dict(resp2.headers))
print()

print("="*60)
print("DIAGNOSIS")
print("="*60)
if data2.get("errors") and "token" in str(data2.get("errors")):
    print("Even /timezone (a free, no-quota endpoint) rejected the key.")
    print("=> This means the key itself is invalid/revoked, NOT a quota issue.")
    print("=> Check dashboard.api-football.com 'My Access' to confirm the live key value.")
else:
    print("/timezone worked but other endpoints failed.")
    print("=> This points to quota exhaustion, not an invalid key.")
