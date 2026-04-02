"""
HTTP client for the Senado Federal open data API.
Base URL: https://legis.senado.leg.br/dadosabertos/
Date format: YYYYMMDD (no separators).
Default format is XML; append .json or set Accept header.
"""

import time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://legis.senado.leg.br/dadosabertos"
_last_call = 0.0
MIN_INTERVAL = 0.5


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
    if not url.endswith(".json"):
        url += ".json"
    resp = httpx.get(url, params=params, timeout=30,
                     headers={"Accept": "application/json"})
    resp.raise_for_status()
    return resp.json()


def to_date_str(iso_date: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD for Senado API."""
    return iso_date.replace("-", "")
