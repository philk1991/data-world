#!/usr/bin/env python3
"""
StatsBomb open data ingestion script.

Fetches all available competitions, matches, events, and lineups from the
StatsBomb open data set and loads them into the lake. No authentication is
required — StatsBomb open data is freely available.

Data is written to the shared DuckLake (see lake.py). All StatsBomb tables
use the raw_sb_* prefix to avoid collisions.

Ingestion is incremental for events and lineups: matches already loaded are
skipped so the script can be re-run safely after partial failures or to pick
up newly published matches.

Configuration (via .env at the project root):
  LAKE_CATALOG / LAKE_DATA_PATH — the DuckLake to write to (see lake.py; defaults
                  work after `task lake:init`)

Usage (run from data-ingestion/):
    python ingest_statsbomb.py
"""
from pathlib import Path
from dotenv import load_dotenv

from lake import connect_lake, lake_settings

from statsbomb.ingestion.competitions import fetch_competitions, load_competitions
from statsbomb.ingestion.matches import fetch_matches, load_matches
from statsbomb.ingestion.events import fetch_events, load_events, get_loaded_match_ids as get_event_match_ids
from statsbomb.ingestion.lineups import fetch_lineups, load_lineups, get_loaded_match_ids as get_lineup_match_ids

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


def main():
    print(f"Connecting to the lake ({lake_settings()[0]})\n")
    conn = connect_lake()

    # 1. Competitions — full replace each run
    print("Fetching competitions...")
    competitions = fetch_competitions()
    load_competitions(conn, competitions)

    # 2. Matches — replace per competition/season
    print("\nFetching matches...")
    for comp in competitions:
        matches = fetch_matches(comp["competition_id"], comp["season_id"])
        load_matches(conn, matches, comp["competition_id"], comp["season_id"])

    # 3. Events and lineups — incremental per match
    print("\nFetching events and lineups (incremental)...")
    loaded_event_ids = get_event_match_ids(conn)
    loaded_lineup_ids = get_lineup_match_ids(conn)

    all_match_rows = conn.execute(
        "SELECT DISTINCT match_id FROM raw_statsbomb.raw_sb_matches WHERE match_status = 'available'"
    ).fetchall()
    all_match_ids = [row[0] for row in all_match_rows]

    total = len(all_match_ids)
    skipped = 0

    for i, match_id in enumerate(all_match_ids, start=1):
        needs_events = match_id not in loaded_event_ids
        needs_lineups = match_id not in loaded_lineup_ids

        if not needs_events and not needs_lineups:
            skipped += 1
            continue

        print(f"  [{i}/{total}] match {match_id}")

        if needs_events:
            events = fetch_events(match_id)
            load_events(conn, events, match_id)

        if needs_lineups:
            lineups = fetch_lineups(match_id)
            load_lineups(conn, lineups, match_id)

    print(f"\n  {total - skipped} matches ingested, {skipped} skipped (already loaded)")
    conn.close()
    print("\nDone. Data written to the lake")


if __name__ == "__main__":
    main()
