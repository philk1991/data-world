"""
Fetch and load OpenF1 pit stops (per session).

API reference: GET https://api.openf1.org/v1/pit?session_key=<key>
Returns one row per pit stop (~40/race session).

DuckDB table: raw_openf1_pit
  Incremental per session_key.
"""
import duckdb
from datetime import datetime, timezone

from ._client import fetch_json, _str_or_none, _int_or_none, _float_or_none


def get_loaded_session_keys(conn: duckdb.DuckDBPyConnection) -> set:
    try:
        rows = conn.execute("SELECT DISTINCT session_key FROM raw_openf1.raw_openf1_pit").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def fetch_pit(session_key: int) -> list[dict]:
    rows = fetch_json("pit", params={"session_key": session_key})
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "session_key":   _int_or_none(r.get("session_key")),
        "meeting_key":   _int_or_none(r.get("meeting_key")),
        "driver_number": _int_or_none(r.get("driver_number")),
        "lap_number":    _int_or_none(r.get("lap_number")),
        "date":          _str_or_none(r.get("date")),
        "pit_duration":  _float_or_none(r.get("pit_duration")),
        "stop_duration": _float_or_none(r.get("stop_duration")),
        "lane_duration": _float_or_none(r.get("lane_duration")),
        "ingested_at":   now,
    } for r in rows]


def load_pit(conn: duckdb.DuckDBPyConnection, records: list[dict], session_key: int) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_openf1")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_openf1.raw_openf1_pit (
            session_key   INTEGER,
            meeting_key   INTEGER,
            driver_number INTEGER,
            lap_number    INTEGER,
            date          VARCHAR,
            pit_duration  DOUBLE,
            stop_duration DOUBLE,
            lane_duration DOUBLE,
            ingested_at   TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_openf1.raw_openf1_pit WHERE session_key = ?", [session_key])
    if records:
        conn.executemany("""
            INSERT INTO raw_openf1.raw_openf1_pit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [[
            r["session_key"], r["meeting_key"], r["driver_number"], r["lap_number"],
            r["date"], r["pit_duration"], r["stop_duration"], r["lane_duration"],
            r["ingested_at"],
        ] for r in records])
        print(f"    pit: {len(records)} rows (session {session_key})")
