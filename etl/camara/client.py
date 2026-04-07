"""
HTTP client for the Câmara dos Deputados open data API.
Base URL: https://dadosabertos.camara.leg.br/api/v2/
Rate limit: throttled to ≤2 req/sec.
"""

import time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
_last_call = 0.0
MIN_INTERVAL = 0.5  # 2 req/sec


def _throttle():
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    _last_call = time.monotonic()


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on network errors and 5xx responses, not 4xx client errors."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return True  # retry on network/timeout errors


@retry(
    stop=stop_after_attempt(6),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception(_is_retryable),
)
def get(path: str, params: dict | None = None) -> dict:
    _throttle()
    url = f"{BASE_URL}{path}"
    resp = httpx.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def paginate(path: str, params: dict | None = None, label: str = "") -> list[dict]:
    """Fetch all pages from a paginated endpoint (max 100 items/page)."""
    params = {**(params or {}), "itens": 100, "pagina": 1}
    results = []
    while True:
        data = get(path, params)
        items = data.get("dados", [])
        results.extend(items)
        if params["pagina"] > 1 or len(items) == 100:
            print(f"    page {params['pagina']} → {len(results)} items{' ' + label if label else ''}", flush=True)
        if len(items) < 100:
            break
        params["pagina"] += 1
    return results
