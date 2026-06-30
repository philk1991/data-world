"""
Shared HTTP client and coercion helpers for the OpenF1 ingestion modules.

OpenF1 (https://openf1.org) is a free, no-auth REST API returning flat top-level
JSON arrays. It rate-limits, so every request goes through `fetch_json`, which
paces calls and retries on HTTP 429 with exponential backoff.

The coercion helpers turn null/missing JSON into typed None so DuckDB inserts
stay well-typed. Factored here (rather than duplicated per module) because the
OpenF1 source has seven entities that all share them.
"""
import time
import requests

BASE_URL = "https://api.openf1.org/v1"

# OpenF1 rate-limits the free tier; keep a minimum gap between requests.
_MIN_INTERVAL = 0.30
_last_call = 0.0


def fetch_json(path: str, params: dict | None = None, retries: int = 5) -> list[dict]:
    """GET BASE_URL/path with pacing + 429 backoff. Returns the JSON list."""
    global _last_call
    delay = 5
    for attempt in range(retries):
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        resp = requests.get(f"{BASE_URL}/{path}", params=params, timeout=30)
        _last_call = time.monotonic()
        if resp.status_code == 429 and attempt < retries - 1:
            print(f"    Rate limited — waiting {delay}s before retry {attempt + 1}/{retries - 1}...")
            time.sleep(delay)
            delay *= 2
            continue
        # OpenF1 returns 404 (not an empty list) when a filtered collection has no
        # rows yet — e.g. a future/early-season session with no laps. Treat as empty.
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        # OpenF1 returns a list on success; a dict usually signals an error payload.
        if isinstance(data, dict):
            raise RuntimeError(f"OpenF1 returned a non-list for {path} {params}: {str(data)[:200]}")
        return data
    resp.raise_for_status()
    return []


def _str_or_none(v):
    return None if v is None else str(v)


def _int_or_none(v):
    return None if v is None else int(v)


def _float_or_none(v):
    return None if v is None else float(v)


def _bool_or_none(v):
    return None if v is None else bool(v)
