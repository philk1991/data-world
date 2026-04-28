"""
Fetch and load StatsBomb lineup data.

StatsBomb reference: sb.lineups(match_id) returns a dict of
{team_name: DataFrame} where each DataFrame row is one player in that team's
starting lineup. Each match has two entries (home and away teams).

DuckDB table: raw_sb_lineups
  Incremental: matches already present are skipped. On retry after a partial
  failure, the match's rows are deleted before reinserting.
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
    """Return the set of match_ids already loaded into raw_sb_lineups."""
    try:
        rows = conn.execute("SELECT DISTINCT match_id FROM raw_statsbomb.raw_sb_lineups").fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()


def fetch_lineups(match_id: int) -> list[dict]:
    """Fetch lineups for one match and flatten both teams to a list of dicts."""
    lineup_dict = _fetch_with_retry(sb.lineups, match_id=match_id)
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for team_name, df in lineup_dict.items():
        for _, row in df.iterrows():
            country_val = row.get("country")
            country_name = (
                country_val.get("name") if isinstance(country_val, dict) else None
            )

            nickname = row.get("player_nickname")
            nickname = str(nickname) if nickname and not pd.isna(nickname) else None

            records.append({
                "match_id":       match_id,
                "team_name":      str(team_name),
                "player_id":      int(row["player_id"]),
                "player_name":    str(row["player_name"]),
                "player_nickname": nickname,
                "jersey_number":  int(row["jersey_number"]),
                "country_name":   country_name,
                "ingested_at":    now,
            })
    return records


def load_lineups(
    conn: duckdb.DuckDBPyConnection,
    lineups: list[dict],
    match_id: int,
) -> None:
    """Insert lineup rows for one match into DuckDB.

    Deletes any existing rows for this match_id first, then bulk-inserts.
    """
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_statsbomb")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_statsbomb.raw_sb_lineups (
            match_id            INTEGER,
            team_name           VARCHAR,
            player_id           INTEGER,
            player_name         VARCHAR,
            player_nickname     VARCHAR,
            jersey_number       INTEGER,
            country_name        VARCHAR,
            ingested_at         TIMESTAMPTZ
        )
    """)

    conn.execute("DELETE FROM raw_statsbomb.raw_sb_lineups WHERE match_id = ?", [match_id])

    if lineups:
        conn.executemany("""
            INSERT INTO raw_statsbomb.raw_sb_lineups VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            [
                l["match_id"], l["team_name"], l["player_id"], l["player_name"],
                l["player_nickname"], l["jersey_number"], l["country_name"],
                l["ingested_at"],
            ]
            for l in lineups
        ])
        print(f"    Lineups: {len(lineups)} rows (match {match_id})")
