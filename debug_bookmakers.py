import requests
import json

key = 'fe244fad09b14ed3c9d7b63af96aa2d7f780720d5407bb87d1e6afc7b55313e6'
r = requests.get('https://api.odds-api.io/v3/bookmakers?apiKey=' + key)
data = r.json()

print('Total bookmakers:', len(data))
print()
print('First bookmaker:')
print(json.dumps(data[0], indent=2))
print()
print('Bookmakers containing "bet" in name:')
for b in data:
    if 'bet' in b.get('name', '').lower():
        print(f"  {b}")
