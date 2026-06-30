# Code templates

Fill these in for the source you're scaffolding. Replace every `<source>`,
`<Source>` (title case for prose), `<entity>`, `<path>`, column names, and types.
Read [conventions.md](conventions.md) for the rules behind the shapes.

The templates use plain `requests` + JSON-native coercion (no pandas) because
generic REST APIs return JSON, not DataFrames. The existing StatsBomb/NBA
modules use library-specific clients (`statsbombpy`, `kagglehub`); a from-scratch
HTTP source uses `requests` directly, as shown here.

---

## Coercion helpers

Paste these near the top of each entity module (or, if a source has many
entities, factor them into `<source>/ingestion/_coerce.py` and import). They
turn `null`/missing JSON into typed `None` so the DuckDB insert stays well-typed.

```python
def _str_or_none(v):
    return None if v is None else str(v)

def _int_or_none(v):
    return None if v is None else int(v)

def _float_or_none(v):
    return None if v is None else float(v)

def _bool_or_none(v):
    return None if v is None else bool(v)
```

---

## Fetch-with-retry helper

```python
import time
import requests

def _fetch_with_retry(url, *, params=None, headers=None, retries=5):
    """GET url, retrying on HTTP 429 with exponential backoff. Returns parsed JSON."""
    delay = 5
    for attempt in range(retries):
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 429 and attempt < retries - 1:
            print(f"    Rate limited — waiting {delay}s before retry {attempt + 1}/{retries - 1}...")
            time.sleep(delay)
            delay *= 2
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
```

---

## Auth headers helper (only if the source needs auth)

```python
import os

def _auth_headers():
    token = os.environ.get("<SOURCE>_API_KEY")
    return {"Authorization": f"Bearer {token}"} if token else {}
```

For an API-key-in-query-param source, pass it through `params=` in
`_fetch_with_retry` instead. For no-auth sources, omit this and the `headers=`
argument entirely.

---

## Entity module — full-replace variant

`data-ingestion/<source>/ingestion/<entity>.py`

```python
"""
Fetch and load <Source> <entity> data.

API reference: GET <base-url>/<path>
Returns <describe the response — e.g. a list of post objects>.

DuckDB table: raw_<source>_<entity>
  Full replace on each run.
"""
import duckdb
from datetime import datetime, timezone

# (paste _str_or_none / _int_or_none / etc. and _fetch_with_retry here,
#  plus _auth_headers if the source needs auth)

BASE_URL = "<base-url>"


def fetch_<entity>() -> list[dict]:
    """Fetch <entity> from the <Source> API and flatten to a list of dicts."""
    payload = _fetch_with_retry(f"{BASE_URL}/<path>")   # add headers=_auth_headers() if needed
    raw_records = payload                # top-level list; OR payload["results"] / payload["data"]
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for r in raw_records:
        records.append({
            "<col_a>":     _int_or_none(r.get("<json_field_a>")),
            "<col_b>":     _str_or_none(r.get("<json_field_b>")),
            "<nested_col>": _str_or_none((r.get("<obj>") or {}).get("<field>")),  # flattened
            "ingested_at": now,
        })
    return records


def load_<entity>(conn: duckdb.DuckDBPyConnection, records: list[dict]) -> None:
    """Replace all <entity> rows in DuckDB (full replace)."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_<source>")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_<source>.raw_<source>_<entity> (
            <col_a>      INTEGER,
            <col_b>      VARCHAR,
            <nested_col> VARCHAR,
            ingested_at  TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_<source>.raw_<source>_<entity>")
    if records:
        conn.executemany("""
            INSERT INTO raw_<source>.raw_<source>_<entity> VALUES (?, ?, ?, ?)
        """, [
            [r["<col_a>"], r["<col_b>"], r["<nested_col>"], r["ingested_at"]]
            for r in records
        ])
        print(f"  Loaded {len(records)} <entity> rows")
```

The `VALUES (?, ?, ?, ?)` placeholder count and the per-row list must match the
column order in `CREATE TABLE` exactly.

---

## Fetch — paginated variant

When the probe reports pagination, loop until the page is empty or there's no
`next`. Two common shapes:

```python
# Shape A — follow a `next` URL (e.g. PokéAPI: {"next": "...", "results": [...]})
def fetch_<entity>() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    records, url = [], f"{BASE_URL}/<path>?limit=100"
    while url:
        payload = _fetch_with_retry(url)
        for r in payload["results"]:
            records.append({ "<col>": _str_or_none(r.get("<field>")), "ingested_at": now })
        url = payload.get("next")
    return records

# Shape B — increment a page/offset param until an empty page comes back
def fetch_<entity>() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    records, page = [], 1
    while True:
        payload = _fetch_with_retry(f"{BASE_URL}/<path>", params={"page": page, "per_page": 100})
        batch = payload if isinstance(payload, list) else payload.get("data", [])
        if not batch:
            break
        for r in batch:
            records.append({ "<col>": _str_or_none(r.get("<field>")), "ingested_at": now })
        page += 1
    return records
```

---

## Entity module — incremental variant

Use when the entity is large, append-only, and keyed. Adds `get_loaded_ids` and
delete-before-insert per key. The entry point drives the skip logic.

```python
def get_loaded_ids(conn: duckdb.DuckDBPyConnection) -> set:
    """Return the set of <key>s already loaded into raw_<source>_<entity>."""
    try:
        rows = conn.execute(
            "SELECT DISTINCT <key> FROM raw_<source>.raw_<source>_<entity>"
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()   # table doesn't exist yet


def fetch_<entity>(<key>) -> list[dict]:
    """Fetch the <entity> rows for one <key>."""
    payload = _fetch_with_retry(f"{BASE_URL}/<path>/{<key>}")
    now = datetime.now(timezone.utc).isoformat()
    return [
        { "<key>": <key>, "<col>": _str_or_none(r.get("<field>")), "ingested_at": now }
        for r in payload["results"]
    ]


def load_<entity>(conn: duckdb.DuckDBPyConnection, records: list[dict], <key>) -> None:
    """Insert one <key>'s rows; delete that key first so retries are clean."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_<source>")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_<source>.raw_<source>_<entity> (
            <key>        INTEGER,
            <col>        VARCHAR,
            ingested_at  TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_<source>.raw_<source>_<entity> WHERE <key> = ?", [<key>])
    if records:
        conn.executemany(
            "INSERT INTO raw_<source>.raw_<source>_<entity> VALUES (?, ?, ?)",
            [[r["<key>"], r["<col>"], r["ingested_at"]] for r in records],
        )
        print(f"    Loaded {len(records)} <entity> rows (<key> {<key>})")
```

---

## Entry point

`data-ingestion/ingest_<source>.py`

```python
#!/usr/bin/env python3
"""
<Source> API ingestion script.

Fetches <entities> from the <Source> API (<base-url>) and loads them into DuckDB
under the raw_<source> schema. <Note auth: none / requires <SOURCE>_API_KEY.>

Configuration (via .env at the project root):
  <SOURCE>_API_KEY — <where to get it>          # omit if no auth
  DUCKDB_PATH      — path to the DuckDB file (shared with other batch sources)

Usage (run from data-ingestion/):
    python ingest_<source>.py
"""
import os
from pathlib import Path
import duckdb
from dotenv import load_dotenv

from <source>.ingestion.<entity_a> import fetch_<entity_a>, load_<entity_a>
from <source>.ingestion.<entity_b> import fetch_<entity_b>, load_<entity_b>

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "spotify.duckdb")


def main():
    db_path = os.environ.get("DUCKDB_PATH", _DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    print(f"Connecting to {db_path}\n")
    conn = duckdb.connect(db_path)

    print("Fetching <entity_a>...")
    load_<entity_a>(conn, fetch_<entity_a>())

    print("\nFetching <entity_b>...")
    load_<entity_b>(conn, fetch_<entity_b>())

    conn.close()
    print(f"\nDone. Data written to {db_path}")


if __name__ == "__main__":
    main()
```

### Entry point — incremental loop

When an entity is incremental, drive the skip logic in `main` like
`ingest_statsbomb.py`:

```python
    loaded = get_loaded_ids(conn)
    keys = [...]                      # the keys to consider (often from a parent table)
    for i, key in enumerate(keys, start=1):
        if key in loaded:
            continue
        print(f"  [{i}/{len(keys)}] <entity> {key}")
        load_<entity>(conn, fetch_<entity>(key), key)
```
