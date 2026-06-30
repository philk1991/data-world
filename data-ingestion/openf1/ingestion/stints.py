"""
Fetch and load OpenF1 stints (per session).

API reference: GET https://api.openf1.org/v1/stints?session_key=<key>
Returns one row per driver tyre stint (~60/race session).

DuckDB table: raw_openf1_stints
  Incremental per session_key.
"""
import duckdb
from datetime import datetime, timezone

from ._client import fetch_json, _str_or_none, _int_or_none


def get_loaded_session_keys(conn: duckdb.DuckDBPyConnection) -> set:
    try:
        rows = conn.execute("SELECT DISTINCT session_key FROM raw_openf1.raw_openf1_stints").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def fetch_stints(session_key: int) -> list[dict]:
    rows = fetch_json("stints", params={"session_key": session_key})
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "meeting_key":       _int_or_none(r.get("meeting_key")),
        "session_key":       _int_or_none(r.get("session_key")),
        "driver_number":     _int_or_none(r.get("driver_number")),
        "stint_number":      _int_or_none(r.get("stint_number")),
        "lap_start":         _int_or_none(r.get("lap_start")),
        "lap_end":           _int_or_none(r.get("lap_end")),
        "compound":          _str_or_none(r.get("compound")),
        "tyre_age_at_start": _int_or_none(r.get("tyre_age_at_start")),
        "ingested_at":       now,
    } for r in rows]


def load_stints(conn: duckdb.DuckDBPyConnection, records: list[dict], session_key: int) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_openf1")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_openf1.raw_openf1_stints (
            meeting_key       INTEGER,
            session_key       INTEGER,
            driver_number     INTEGER,
            stint_number      INTEGER,
            lap_start         INTEGER,
            lap_end           INTEGER,
            compound          VARCHAR,
            tyre_age_at_start INTEGER,
            ingested_at       TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_openf1.raw_openf1_stints WHERE session_key = ?", [session_key])
    if records:
        conn.executemany("""
            INSERT INTO raw_openf1.raw_openf1_stints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [[
            r["meeting_key"], r["session_key"], r["driver_number"], r["stint_number"],
            r["lap_start"], r["lap_end"], r["compound"], r["tyre_age_at_start"],
            r["ingested_at"],
        ] for r in records])
        print(f"    stints: {len(records)} rows (session {session_key})")
