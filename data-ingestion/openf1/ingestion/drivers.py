"""
Fetch and load OpenF1 drivers (per session).

API reference: GET https://api.openf1.org/v1/drivers?session_key=<key>
Returns the ~20 drivers entered for one session.

DuckDB table: raw_openf1_drivers
  Incremental per session_key: sessions already loaded are skipped; a session's
  rows are deleted before reinsert so retries after a partial run are clean.
  headshot_url is dropped (media link).
"""
import duckdb
from datetime import datetime, timezone

from ._client import fetch_json, _str_or_none, _int_or_none


def get_loaded_session_keys(conn: duckdb.DuckDBPyConnection) -> set:
    try:
        rows = conn.execute("SELECT DISTINCT session_key FROM raw_openf1.raw_openf1_drivers").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def fetch_drivers(session_key: int) -> list[dict]:
    rows = fetch_json("drivers", params={"session_key": session_key})
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "meeting_key":    _int_or_none(r.get("meeting_key")),
        "session_key":    _int_or_none(r.get("session_key")),
        "driver_number":  _int_or_none(r.get("driver_number")),
        "broadcast_name": _str_or_none(r.get("broadcast_name")),
        "full_name":      _str_or_none(r.get("full_name")),
        "name_acronym":   _str_or_none(r.get("name_acronym")),
        "team_name":      _str_or_none(r.get("team_name")),
        "team_colour":    _str_or_none(r.get("team_colour")),
        "first_name":     _str_or_none(r.get("first_name")),
        "last_name":      _str_or_none(r.get("last_name")),
        "country_code":   _str_or_none(r.get("country_code")),
        "ingested_at":    now,
    } for r in rows]


def load_drivers(conn: duckdb.DuckDBPyConnection, records: list[dict], session_key: int) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_openf1")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_openf1.raw_openf1_drivers (
            meeting_key    INTEGER,
            session_key    INTEGER,
            driver_number  INTEGER,
            broadcast_name VARCHAR,
            full_name      VARCHAR,
            name_acronym   VARCHAR,
            team_name      VARCHAR,
            team_colour    VARCHAR,
            first_name     VARCHAR,
            last_name      VARCHAR,
            country_code   VARCHAR,
            ingested_at    TIMESTAMPTZ
        )
    """)
    conn.execute("DELETE FROM raw_openf1.raw_openf1_drivers WHERE session_key = ?", [session_key])
    if records:
        conn.executemany("""
            INSERT INTO raw_openf1.raw_openf1_drivers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [[
            r["meeting_key"], r["session_key"], r["driver_number"], r["broadcast_name"],
            r["full_name"], r["name_acronym"], r["team_name"], r["team_colour"],
            r["first_name"], r["last_name"], r["country_code"], r["ingested_at"],
        ] for r in records])
        print(f"    drivers: {len(records)} rows (session {session_key})")
