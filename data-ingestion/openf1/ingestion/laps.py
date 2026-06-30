"""
Fetch and load OpenF1 laps (per session).

API reference: GET https://api.openf1.org/v1/laps?session_key=<key>
Returns one row per driver per lap (~1100/race session).

DuckDB table: raw_openf1_laps
  Incremental per session_key. The segments_sector_1/2/3 fields are arrays of
  per-marshalling-sector codes — dropped from raw (arrays belong in their own
  entity or in dbt, not in a flat raw table). i1/i2/st speeds are intermediate
  and finish-line speed-trap readings.
"""
import duckdb
from datetime import datetime, timezone

from ._client import fetch_json, _str_or_none, _int_or_none, _float_or_none, _bool_or_none


def get_loaded_session_keys(conn: duckdb.DuckDBPyConnection) -> set:
    try:
        rows = conn.execute("SELECT DISTINCT session_key FROM raw_openf1.raw_openf1_laps").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def fetch_laps(session_key: int) -> list[dict]:
    rows = fetch_json("laps", params={"session_key": session_key})
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "meeting_key":       _int_or_none(r.get("meeting_key")),
        "session_key":       _int_or_none(r.get("session_key")),
        "driver_number":     _int_or_none(r.get("driver_number")),
        "lap_number":        _int_or_none(r.get("lap_number")),
        "date_start":        _str_or_none(r.get("date_start")),
        "lap_duration":      _float_or_none(r.get("lap_duration")),
        "duration_sector_1": _float_or_none(r.get("duration_sector_1")),
        "duration_sector_2": _float_or_none(r.get("duration_sector_2")),
        "duration_sector_3": _float_or_none(r.get("duration_sector_3")),
        "i1_speed":          _int_or_none(r.get("i1_speed")),
        "i2_speed":          _int_or_none(r.get("i2_speed")),
        "st_speed":          _int_or_none(r.get("st_speed")),
        "is_pit_out_lap":    _bool_or_none(r.get("is_pit_out_lap")),
        "ingested_at":       now,
    } for r in rows]


def load_laps(conn: duckdb.DuckDBPyConnection, records: list[dict], session_key: int) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_openf1")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_openf1.raw_openf1_laps (
            meeting_key       INTEGER,
            session_key       INTEGER,
            driver_number     INTEGER,
            lap_number        INTEGER,
            date_start        VARCHAR,
            lap_duration      DOUBLE,
            duration_sector_1 DOUBLE,
            duration_sector_2 DOUBLE,
            duration_sector_3 DOUBLE,
            i1_speed          INTEGER,
            i2_speed          INTEGER,
            st_speed          INTEGER,
            is_pit_out_lap    BOOLEAN,
            ingested_at       TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_openf1.raw_openf1_laps WHERE session_key = ?", [session_key])
    if records:
        conn.executemany("""
            INSERT INTO raw_openf1.raw_openf1_laps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [[
            r["meeting_key"], r["session_key"], r["driver_number"], r["lap_number"],
            r["date_start"], r["lap_duration"], r["duration_sector_1"], r["duration_sector_2"],
            r["duration_sector_3"], r["i1_speed"], r["i2_speed"], r["st_speed"],
            r["is_pit_out_lap"], r["ingested_at"],
        ] for r in records])
        print(f"    laps: {len(records)} rows (session {session_key})")
