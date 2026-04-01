"""
Fetch and load StatsBomb event data.

StatsBomb reference: sb.events(match_id) returns all events in a match — one
row per event. A match typically contains 3,000–4,000 events covering all
action types: Pass, Shot, Dribble, Carry, Pressure, Ball Receipt, etc.

Only the universal event envelope columns are stored. Type-specific columns
(shot_outcome, pass_length, etc.) are intentionally excluded from raw at this
stage — they are sparse and can be added as separate tables later.

DuckDB table: raw_sb_events
  Incremental: matches already present are skipped. On retry after a partial
  failure, the match's rows are deleted before reinserting.

Note: 'type' is a SQL reserved word — stored as 'event_type'.
"""
import time
import duckdb
import pandas as pd
import requests
from datetime import datetime, timezone

import statsbombpy.sb as sb


def _fetch_with_retry(fn, *args, retries: int = 5, **kwargs):
    """Call fn(*args, **kwargs), retrying on HTTP 429 with exponential backoff."""
    delay = 10
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429 and attempt < retries - 1:
                print(f"    Rate limited — waiting {delay}s before retry {attempt + 1}/{retries - 1}...")
                time.sleep(delay)
                delay *= 2
            else:
                raise


def get_loaded_match_ids(conn: duckdb.DuckDBPyConnection) -> set[int]:
    """Return the set of match_ids already fully loaded into raw_sb_events."""
    try:
        rows = conn.execute("SELECT DISTINCT match_id FROM raw_sb_events").fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()


def _str_or_none(val) -> str | None:
    """Return val as a string, or None if null/NaN."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return str(val)


def _int_or_none(val) -> int | None:
    """Return val as an int, or None if null/NaN."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return int(val)


def fetch_events(match_id: int) -> list[dict]:
    """Fetch all events for one match and flatten to a list of dicts.

    statsbombpy already flattens nested fields — type, play_pattern,
    possession_team, team, player, and player_id are all plain scalars.
    """
    df = _fetch_with_retry(sb.events, match_id=match_id)
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for _, row in df.iterrows():
        loc = row.get("location")
        location_x = float(loc[0]) if isinstance(loc, list) and len(loc) >= 2 else None
        location_y = float(loc[1]) if isinstance(loc, list) and len(loc) >= 2 else None

        duration = row.get("duration")
        duration = float(duration) if duration is not None and not pd.isna(duration) else None

        records.append({
            "event_id":         str(row["id"]),
            "match_id":         match_id,
            "event_index":      int(row["index"]),
            "period":           int(row["period"]),
            "timestamp":        _str_or_none(row.get("timestamp")),
            "minute":           int(row["minute"]),
            "second":           int(row["second"]),
            "event_type":       _str_or_none(row.get("type")),
            "possession":       int(row["possession"]),
            "possession_team":  _str_or_none(row.get("possession_team")),
            "play_pattern":     _str_or_none(row.get("play_pattern")),
            "team":             _str_or_none(row.get("team")),
            "player_id":        _int_or_none(row.get("player_id")),
            "player_name":      _str_or_none(row.get("player")),
            "location_x":       location_x,
            "location_y":       location_y,
            "duration":         duration,
            "ingested_at":      now,
        })
    return records


def load_events(
    conn: duckdb.DuckDBPyConnection,
    events: list[dict],
    match_id: int,
) -> None:
    """Insert events for one match into DuckDB.

    Deletes any existing rows for this match_id first (handles partial-failure
    retries), then bulk-inserts all events.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_sb_events (
            event_id            VARCHAR,
            match_id            INTEGER,
            event_index         INTEGER,
            period              INTEGER,
            timestamp           VARCHAR,
            minute              INTEGER,
            second              INTEGER,
            event_type          VARCHAR,
            possession          INTEGER,
            possession_team     VARCHAR,
            play_pattern        VARCHAR,
            team                VARCHAR,
            player_id           INTEGER,
            player_name         VARCHAR,
            location_x          DOUBLE,
            location_y          DOUBLE,
            duration            DOUBLE,
            ingested_at         TIMESTAMPTZ
        )
    """)

    conn.execute("DELETE FROM raw_sb_events WHERE match_id = ?", [match_id])

    if events:
        conn.executemany("""
            INSERT INTO raw_sb_events VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            [
                e["event_id"], e["match_id"], e["event_index"], e["period"],
                e["timestamp"], e["minute"], e["second"], e["event_type"],
                e["possession"], e["possession_team"], e["play_pattern"], e["team"],
                e["player_id"], e["player_name"],
                e["location_x"], e["location_y"], e["duration"],
                e["ingested_at"],
            ]
            for e in events
        ])
        print(f"    Events: {len(events)} rows (match {match_id})")
