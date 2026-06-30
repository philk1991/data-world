#!/usr/bin/env python3
"""
Probe a REST API endpoint and suggest a DuckDB raw-table schema.

Fetches one response, locates the list of records inside it, scans a sample of
those records, and prints — per top-level field — a suggested DuckDB column
type, a sample value, the null rate across the sample, and a flag for nested
objects/arrays. It also reports whether the response looks paginated.

Run this in Step 2 of the ingest-api-source skill, once per entity endpoint, so
the generated CREATE TABLE reflects the real response rather than the docs.

Usage:
    python probe_endpoint.py <url> [--header "Header: value"]... [--limit N]

Examples:
    python probe_endpoint.py https://jsonplaceholder.typicode.com/users
    python probe_endpoint.py https://pokeapi.co/api/v2/pokemon?limit=50
    python probe_endpoint.py https://api.example.com/v1/orders --header "Authorization: Bearer $TOKEN"
"""
import argparse
import json
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    sys.exit("requests is not installed — activate the venv: source .venv/bin/activate")

# Keys commonly wrapping the actual list of records in a JSON response.
LIST_KEYS = ("results", "data", "items", "records", "rows", "elements", "content")
# Keys that signal pagination when present at the top level.
PAGINATION_KEYS = ("next", "next_page", "next_url", "count", "total", "total_count",
                   "page", "per_page", "offset", "cursor", "has_more", "links")


def find_records(payload):
    """Return (records_list, records_key) — where the list of entities lives."""
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, dict):
        for key in LIST_KEYS:
            if isinstance(payload.get(key), list):
                return payload[key], key
        # Fall back to the first list-of-dicts value found.
        for key, val in payload.items():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                return val, key
        # A single object response (not a collection).
        return [payload], None
    return [], None


def looks_like_datetime(value):
    if not isinstance(value, str) or len(value) < 8:
        return False
    probe = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(probe)
        return True
    except ValueError:
        return False


def duckdb_type(values):
    """Infer a DuckDB type from the non-null sample values of one field."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "VARCHAR", "all-null in sample — confirm type from API docs"
    sample = non_null[0]
    if isinstance(sample, bool):
        return "BOOLEAN", ""
    if isinstance(sample, int):
        if any(abs(v) > 2_147_483_647 for v in non_null if isinstance(v, int)):
            return "BIGINT", "values exceed INT32 range"
        return "INTEGER", ""
    if isinstance(sample, float):
        return "DOUBLE", ""
    if isinstance(sample, dict):
        return "NESTED_OBJECT", "flatten the fields you need (obj_field) or drop"
    if isinstance(sample, list):
        return "NESTED_ARRAY", "drop in raw, or split into its own entity"
    if isinstance(sample, str):
        if all(looks_like_datetime(v) for v in non_null if isinstance(v, str)):
            return "VARCHAR", "ISO datetime — keep VARCHAR in raw, parse in dbt staging"
        return "VARCHAR", ""
    return "VARCHAR", f"unhandled JSON type {type(sample).__name__}"


def main():
    ap = argparse.ArgumentParser(description="Probe a REST endpoint and suggest a DuckDB schema.")
    ap.add_argument("url")
    ap.add_argument("--header", action="append", default=[],
                    help='HTTP header "Name: value" (repeatable)')
    ap.add_argument("--limit", type=int, default=50, help="max records to scan (default 50)")
    args = ap.parse_args()

    headers = {}
    for h in args.header:
        if ":" not in h:
            sys.exit(f"bad --header (need 'Name: value'): {h}")
        name, _, value = h.partition(":")
        headers[name.strip()] = value.strip()

    try:
        resp = requests.get(args.url, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.JSONDecodeError:
        sys.exit("response was not JSON — this skill is for JSON REST APIs")
    except requests.exceptions.RequestException as e:
        sys.exit(f"request failed: {e}")

    records, records_key = find_records(payload)
    if not records:
        sys.exit("could not find any records in the response — inspect it manually:\n"
                 + json.dumps(payload, indent=2)[:2000])

    sample = [r for r in records[:args.limit] if isinstance(r, dict)]
    if not sample:
        print("Records are scalars, not objects. First few:", records[:10])
        sys.exit(0)

    # Union of fields across the sample (objects may omit nulls).
    fields = []
    for r in sample:
        for k in r:
            if k not in fields:
                fields.append(k)

    paginated = isinstance(payload, dict) and any(k in payload for k in PAGINATION_KEYS)

    print(f"\nEndpoint : {args.url}")
    print(f"Records  : {len(records)} in response, scanned {len(sample)}")
    print(f"Records key : {records_key if records_key else '(top-level array)'}"
          + (f"   → index payload[{records_key!r}] in fetch_" if records_key else ""))
    print(f"Paginated   : {'YES — use the paginated fetch_ variant' if paginated else 'no'}")
    if paginated:
        present = [k for k in PAGINATION_KEYS if isinstance(payload, dict) and k in payload]
        print(f"  pagination keys present: {present}")
    print(f"\n{'column':<24} {'duckdb_type':<16} {'null%':>6}  {'sample':<28} note")
    print("-" * 100)
    for f in fields:
        values = [r.get(f) for r in sample]
        dtype, note = duckdb_type(values)
        null_pct = round(100 * sum(v is None for v in values) / len(values))
        sample_val = next((v for v in values if v is not None), None)
        sample_str = json.dumps(sample_val)[:26] if sample_val is not None else "—"
        col = f.lower().replace(" ", "_")
        print(f"{col:<24} {dtype:<16} {null_pct:>5}%  {sample_str:<28} {note}")

    print("\nRemember: add an `ingested_at TIMESTAMPTZ` column (stamped in fetch_), "
          "flatten or drop NESTED_* fields, and name the table raw_<source>_<entity>.")


if __name__ == "__main__":
    main()
