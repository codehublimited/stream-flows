import requests
import json

BASE_URL = BASE_URL = "https://stream-flows-1.onrender.com"

print("="*60)
print("SPORTSDB DEPLOYED BACKEND DIAGNOSTIC")
print("="*60)

def check(path, method="GET", **kwargs):
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=10, **kwargs)
        print(f"{method} {path} -> {resp.status_code}")
        return resp
    except requests.exceptions.RequestException as e:
        print(f"{method} {path} -> FAILED: {e}")
        return None

print("\n--- Basic health ---")
check("/health")
check("/db-test")

print("\n--- Core resources ---")
check("/leagues/")
check("/teams/")
check("/matches/")
check("/predictions/")
check("/seasons/")

print("\n--- Telegram auth (checking if it exists at all) ---")
check("/auth/telegram", method="POST", json={"initData": "test"})
check("/users/")
check("/users/me")

print("\n--- CORS check ---")
resp = check("/leagues/", method="OPTIONS")
if resp:
    print("Access-Control-Allow-Origin:", resp.headers.get("access-control-allow-origin"))

print("\n--- API docs ---")
check("/docs")
check("/openapi.json")

print("\n" + "="*60)
print("Replace BASE_URL above with your real deployed URL and re-run")
print("="*60)
