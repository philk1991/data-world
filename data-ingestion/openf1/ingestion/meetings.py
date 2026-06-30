"""
Fetch and load OpenF1 meetings (Grand Prix weekends).

API reference: GET https://api.openf1.org/v1/meetings?year=<year>
Returns one row per race weekend in the season (~25/year).

DuckDB table: raw_openf1_meetings
  Full replace per run (small table). Media-URL fields (country_flag,
  circuit_image, circuit_info_url) are dropped — raw keeps the analytical
  columns; links can be re-derived if ever needed.
"""
import duckdb
from datetime import datetime, timezone

from ._client import fetch_json, _str_or_none, _int_or_none, _bool_or_none


def fetch_meetings(year: int) -> list[dict]:
    """Fetch all meetings for one season."""
    rows = fetch_json("meetings", params={"year": year})
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "meeting_key":            _int_or_none(r.get("meeting_key")),
        "meeting_name":           _str_or_none(r.get("meeting_name")),
        "meeting_official_name":  _str_or_none(r.get("meeting_official_name")),
        "location":               _str_or_none(r.get("location")),
        "country_key":            _int_or_none(r.get("country_key")),
        "country_code":           _str_or_none(r.get("country_code")),
        "country_name":           _str_or_none(r.get("country_name")),
        "circuit_key":            _int_or_none(r.get("circuit_key")),
        "circuit_short_name":     _str_or_none(r.get("circuit_short_name")),
        "gmt_offset":             _str_or_none(r.get("gmt_offset")),
        "date_start":             _str_or_none(r.get("date_start")),
        "date_end":               _str_or_none(r.get("date_end")),
        "year":                   _int_or_none(r.get("year")),
        "is_cancelled":           _bool_or_none(r.get("is_cancelled")),
        "ingested_at":            now,
    } for r in rows]


def load_meetings(conn: duckdb.DuckDBPyConnection, records: list[dict], year: int) -> None:
    """Replace the meeting rows for one season (delete that year, then insert).

    Deleting per-year rather than truncating lets the entry point loop several
    seasons into the same table without each year wiping the previous one, while
    staying idempotent on re-run.
    """
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_openf1")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_openf1.raw_openf1_meetings (
            meeting_key           INTEGER,
            meeting_name          VARCHAR,
            meeting_official_name VARCHAR,
            location              VARCHAR,
            country_key           INTEGER,
            country_code          VARCHAR,
            country_name          VARCHAR,
            circuit_key           INTEGER,
            circuit_short_name    VARCHAR,
            gmt_offset            VARCHAR,
            date_start            VARCHAR,
            date_end              VARCHAR,
            year                  INTEGER,
            is_cancelled          BOOLEAN,
            ingested_at           TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_openf1.raw_openf1_meetings WHERE year = ?", [year])
    if records:
        conn.executemany("""
            INSERT INTO raw_openf1.raw_openf1_meetings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [[
            r["meeting_key"], r["meeting_name"], r["meeting_official_name"], r["location"],
            r["country_key"], r["country_code"], r["country_name"], r["circuit_key"],
            r["circuit_short_name"], r["gmt_offset"], r["date_start"], r["date_end"],
            r["year"], r["is_cancelled"], r["ingested_at"],
        ] for r in records])
        print(f"  Loaded {len(records)} meetings ({year})")
