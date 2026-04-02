"""
HTTP client for the Câmara dos Deputados open data API.
Base URL: https://dadosabertos.camara.leg.br/api/v2/
Rate limit: throttled to ≤2 req/sec.
"""

import time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
_last_call = 0.0
MIN_INTERVAL = 0.5  # 2 req/sec


def _throttle():
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    _last_call = time.monotonic()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get(path: str, params: dict | None = None) -> dict:
    _throttle()
    url = f"{BASE_URL}{path}"
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def paginate(path: str, params: dict | None = None) -> list[dict]:
    """Fetch all pages from a paginated endpoint (max 100 items/page)."""
    params = {**(params or {}), "itens": 100, "pagina": 1}
    results = []
    while True:
        data = get(path, params)
        items = data.get("dados", [])
        results.extend(items)
        if len(items) < 100:
            break
        params["pagina"] += 1
    return results
