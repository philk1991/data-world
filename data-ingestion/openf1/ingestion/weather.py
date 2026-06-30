"""
Fetch and load OpenF1 weather (per session).

API reference: GET https://api.openf1.org/v1/weather?session_key=<key>
Returns a time series of weather readings during the session (~150/race session).

DuckDB table: raw_openf1_weather
  Incremental per session_key.
"""
import duckdb
from datetime import datetime, timezone

from ._client import fetch_json, _str_or_none, _int_or_none, _float_or_none


def get_loaded_session_keys(conn: duckdb.DuckDBPyConnection) -> set:
    try:
        rows = conn.execute("SELECT DISTINCT session_key FROM raw_openf1.raw_openf1_weather").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def fetch_weather(session_key: int) -> list[dict]:
    rows = fetch_json("weather", params={"session_key": session_key})
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "session_key":       _int_or_none(r.get("session_key")),
        "meeting_key":       _int_or_none(r.get("meeting_key")),
        "date":              _str_or_none(r.get("date")),
        "air_temperature":   _float_or_none(r.get("air_temperature")),
        "track_temperature": _float_or_none(r.get("track_temperature")),
        "humidity":          _float_or_none(r.get("humidity")),
        "pressure":          _float_or_none(r.get("pressure")),
        "rainfall":          _int_or_none(r.get("rainfall")),
        "wind_direction":    _int_or_none(r.get("wind_direction")),
        "wind_speed":        _float_or_none(r.get("wind_speed")),
        "ingested_at":       now,
    } for r in rows]


def load_weather(conn: duckdb.DuckDBPyConnection, records: list[dict], session_key: int) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_openf1")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_openf1.raw_openf1_weather (
            session_key       INTEGER,
            meeting_key       INTEGER,
            date              VARCHAR,
            air_temperature   DOUBLE,
            track_temperature DOUBLE,
            humidity          DOUBLE,
            pressure          DOUBLE,
            rainfall          INTEGER,
            wind_direction    INTEGER,
            wind_speed        DOUBLE,
            ingested_at       TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_openf1.raw_openf1_weather WHERE session_key = ?", [session_key])
    if records:
        conn.executemany("""
            INSERT INTO raw_openf1.raw_openf1_weather VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [[
            r["session_key"], r["meeting_key"], r["date"], r["air_temperature"],
            r["track_temperature"], r["humidity"], r["pressure"], r["rainfall"],
            r["wind_direction"], r["wind_speed"], r["ingested_at"],
        ] for r in records])
        print(f"    weather: {len(records)} rows (session {session_key})")
