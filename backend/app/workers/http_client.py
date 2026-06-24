import requests


def safe_get(url: str, headers: dict = None, params: dict = None, timeout: int = 15):
    """
    Wrapper around requests.get with consistent timeout and error handling.
    Returns parsed JSON dict on success, or None on failure (logs the reason).
    """
    try:
        response = requests.get(url, headers=headers or {}, params=params or {}, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"TIMEOUT: {url}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP ERROR {response.status_code} for {url}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"REQUEST FAILED for {url}: {e}")
        return None
