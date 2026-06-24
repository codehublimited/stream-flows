import requests
import time
import re

API_KEY = "fe244fad09b14ed3c9d7b63af96aa2d7f780720d5407bb87d1e6afc7b55313e6"

def wait_for_rate_limit():
    url = f"https://api.odds-api.io/v3/events?sport=football&apiKey={API_KEY}"
    while True:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return True
        elif r.status_code == 429:
            error_msg = r.json().get("error", "")
            match = re.search(r"resets in (\d+) minutes? and (\d+) seconds?", error_msg)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                wait = minutes * 60 + seconds + 5
            else:
                wait = 3600
            print(f"Rate limit hit. Waiting {wait} seconds...")
            time.sleep(wait)
        else:
            print(f"Error: {r.status_code}")
            time.sleep(60)

if __name__ == "__main__":
    print("Waiting for rate limit to reset...")
    wait_for_rate_limit()
    print("Rate limit reset. You can now run the script.")
