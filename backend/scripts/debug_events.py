import requests, json
key = 'fe244fad09b14ed3c9d7b63af96aa2d7f780720d5407bb87d1e6afc7b55313e6'
r = requests.get('https://api.odds-api.io/v3/events?sport=football&apiKey=' + key)
data = r.json()
print('Top-level type:', type(data))
if isinstance(data, dict):
    print('Keys:', list(data.keys()))
    for k, v in data.items():
        if isinstance(v, list) and v:
            print(f'Key "{k}" is a list with {len(v)} items')
            ev = v[0]
            print('First event keys:', list(ev.keys()))
            print('First event sample:', json.dumps(ev, indent=2)[:500])
            break
elif isinstance(data, list):
    print('It is a list with', len(data), 'items')
    if data:
        ev = data[0]
        print('First event keys:', list(ev.keys()))
        print('First event sample:', json.dumps(ev, indent=2)[:500])
