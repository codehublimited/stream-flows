import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs
from typing import Dict, Optional, Tuple

BOT_TOKEN = "YOUR_BOT_TOKEN"  # Replace with your actual bot token

def verify_telegram_init_data(init_data: str, bot_token: str = BOT_TOKEN) -> Tuple[bool, Optional[Dict]]:
    if not init_data:
        return False, None

    parsed = parse_qs(init_data)
    hash_value = parsed.get("hash", [None])[0]
    if not hash_value:
        return False, None

    data_without_hash = {k: v[0] for k, v in parsed.items() if k != "hash"}
    sorted_keys = sorted(data_without_hash.keys())
    data_check_string = "\n".join([f"{k}={data_without_hash[k]}" for k in sorted_keys])

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if computed_hash != hash_value:
        return False, None

    auth_date = data_without_hash.get("auth_date")
    if auth_date:
        try:
            auth_timestamp = int(auth_date)
            current_time = int(time.time())
            if current_time - auth_timestamp > 86400:
                print("Warning: auth_date is older than 24 hours")
        except ValueError:
            pass

    user_data = None
    if "user" in data_without_hash:
        try:
            user_data = json.loads(data_without_hash["user"])
        except json.JSONDecodeError:
            pass

    return True, user_data

if __name__ == "__main__":
    test_data = "query_id=AAHdF6IQAAAAAN0XohD&user=%7B%22id%22%3A123456%2C%22first_name%22%3A%22John%22%7D&auth_date=1623456789&hash=abcdef1234567890"
    is_valid, user = verify_telegram_init_data(test_data)
    print(f"Valid: {is_valid}, User: {user}")
