"""
Fetch and load OpenF1 sessions (practice / qualifying / race within a weekend).

API reference: GET https://api.openf1.org/v1/sessions?year=<year>
Returns one row per session in the season (~123/year).

DuckDB table: raw_openf1_sessions
  Full replace per run. The entry point reads session_key from this table to
  drive the per-session incremental entities (drivers, laps, pit, stints, weather).
"""
import duckdb
from datetime import datetime, timezone

from ._client import fetch_json, _str_or_none, _int_or_none, _bool_or_none


def fetch_sessions(year: int) -> list[dict]:
    """Fetch all sessions for one season."""
    rows = fetch_json("sessions", params={"year": year})
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "session_key":        _int_or_none(r.get("session_key")),
        "session_type":       _str_or_none(r.get("session_type")),
        "session_name":       _str_or_none(r.get("session_name")),
        "date_start":         _str_or_none(r.get("date_start")),
        "date_end":           _str_or_none(r.get("date_end")),
        "meeting_key":        _int_or_none(r.get("meeting_key")),
        "circuit_key":        _int_or_none(r.get("circuit_key")),
        "circuit_short_name": _str_or_none(r.get("circuit_short_name")),
        "country_code":       _str_or_none(r.get("country_code")),
        "country_name":       _str_or_none(r.get("country_name")),
        "location":           _str_or_none(r.get("location")),
        "gmt_offset":         _str_or_none(r.get("gmt_offset")),
        "year":               _int_or_none(r.get("year")),
        "is_cancelled":       _bool_or_none(r.get("is_cancelled")),
        "ingested_at":        now,
    } for r in rows]


def load_sessions(conn: duckdb.DuckDBPyConnection, records: list[dict], year: int) -> None:
    """Replace the session rows for one season (delete that year, then insert).

    Per-year delete lets several seasons accumulate in one table while staying
    idempotent — see load_meetings for the rationale.
    """
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_openf1")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_openf1.raw_openf1_sessions (
            session_key        INTEGER,
            session_type       VARCHAR,
            session_name       VARCHAR,
            date_start         VARCHAR,
            date_end           VARCHAR,
            meeting_key        INTEGER,
            circuit_key        INTEGER,
            circuit_short_name VARCHAR,
            country_code       VARCHAR,
            country_name       VARCHAR,
            location           VARCHAR,
            gmt_offset         VARCHAR,
            year               INTEGER,
            is_cancelled       BOOLEAN,
            ingested_at        TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_openf1.raw_openf1_sessions WHERE year = ?", [year])
    if records:
        conn.executemany("""
            INSERT INTO raw_openf1.raw_openf1_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [[
            r["session_key"], r["session_type"], r["session_name"], r["date_start"],
            r["date_end"], r["meeting_key"], r["circuit_key"], r["circuit_short_name"],
            r["country_code"], r["country_name"], r["location"], r["gmt_offset"],
            r["year"], r["is_cancelled"], r["ingested_at"],
        ] for r in records])
        print(f"  Loaded {len(records)} sessions ({year})")
