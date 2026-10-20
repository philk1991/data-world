#!/usr/bin/env python3
"""
OpenF1 API ingestion script.

Fetches Formula 1 timing data from the OpenF1 API (https://openf1.org) and loads
it into DuckDB under the raw_openf1 schema. No authentication is required.

Two top-level tables (meetings, sessions) are full-replaced per season. The five
per-session tables (drivers, laps, pit, stints, weather) are incremental: each
session already loaded is skipped, so the script can be re-run safely to resume
after a partial run or to pick up newly completed sessions.

Configuration (via .env at the project root or environment variables):
  LAKE_CATALOG / LAKE_DATA_PATH — the DuckLake to write to (see lake.py; defaults
                  work after `task lake:init`)
  OPENF1_START_YEAR    — first season to ingest (default 2024); the script ingests
                         every season from this year through the current calendar
                         year inclusive (2024 onwards)
  OPENF1_END_YEAR      — last season to ingest (default: current calendar year)
  OPENF1_SESSION_LIMIT — optional cap on number of sessions processed per run,
                         newest first (handy for a quick first run; unset = all)

Usage (run from data-ingestion/):
    python ingest_openf1.py
"""
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

from lake import connect_lake, lake_settings

from openf1.ingestion.meetings import fetch_meetings, load_meetings
from openf1.ingestion.sessions import fetch_sessions, load_sessions
from openf1.ingestion.drivers import fetch_drivers, load_drivers, get_loaded_session_keys as drivers_loaded
from openf1.ingestion.laps import fetch_laps, load_laps, get_loaded_session_keys as laps_loaded
from openf1.ingestion.pit import fetch_pit, load_pit, get_loaded_session_keys as pit_loaded
from openf1.ingestion.stints import fetch_stints, load_stints, get_loaded_session_keys as stints_loaded
from openf1.ingestion.weather import fetch_weather, load_weather, get_loaded_session_keys as weather_loaded

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# Per-session entities, paired with their fetch/load/loaded-keys functions.
PER_SESSION = [
    ("drivers", fetch_drivers, load_drivers, drivers_loaded),
    ("laps",    fetch_laps,    load_laps,    laps_loaded),
    ("pit",     fetch_pit,     load_pit,     pit_loaded),
    ("stints",  fetch_stints,  load_stints,  stints_loaded),
    ("weather", fetch_weather, load_weather, weather_loaded),
]


def main():
    start_year = int(os.environ.get("OPENF1_START_YEAR", "2024"))
    end_year = int(os.environ.get("OPENF1_END_YEAR", str(date.today().year)))
    limit = os.environ.get("OPENF1_SESSION_LIMIT")
    limit = int(limit) if limit else None
    years = list(range(start_year, end_year + 1))

    print(f"Connecting to the lake ({lake_settings()[0]})")
    print(f"Seasons: {start_year}–{end_year}{f'  (session limit: {limit})' if limit else ''}\n")
    conn = connect_lake()

    # 1. Meetings + sessions — full replace per season, looped across the range.
    for year in years:
        print(f"Fetching meetings + sessions for {year}...")
        load_meetings(conn, fetch_meetings(year), year)
        load_sessions(conn, fetch_sessions(year), year)

    # 2. Per-session entities — incremental, newest sessions first, across all years.
    placeholders = ",".join("?" for _ in years)
    session_keys = [r[0] for r in conn.execute(
        f"SELECT session_key FROM raw_openf1.raw_openf1_sessions "
        f"WHERE year IN ({placeholders}) ORDER BY date_start DESC",
        years,
    ).fetchall()]
    if limit:
        session_keys = session_keys[:limit]

    loaded = {name: fn(conn) for name, _, _, fn in PER_SESSION}

    print(f"\nFetching per-session data for {len(session_keys)} sessions (incremental)...")
    total = len(session_keys)
    for i, sk in enumerate(session_keys, start=1):
        pending = [(name, fetch, load) for name, fetch, load, _ in PER_SESSION
                   if sk not in loaded[name]]
        if not pending:
            continue
        print(f"  [{i}/{total}] session {sk}")
        for name, fetch, load in pending:
            load(conn, fetch(sk), sk)

    conn.close()
    print("\nDone. Data written to the lake")


if __name__ == "__main__":
    main()
