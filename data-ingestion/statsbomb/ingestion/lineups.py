"""
Fetch and load StatsBomb lineup data.

StatsBomb reference: sb.lineups(match_id) returns a dict of
{team_name: DataFrame} where each DataFrame row is one player in that team's
starting lineup. Each match has two entries (home and away teams).

DuckDB table: raw_sb_lineups
  Incremental: matches already present are skipped. On retry after a partial
  failure, the match's rows are deleted before reinserting.
"""
import duckdb
import pandas as pd
from datetime import datetime, timezone

import statsbombpy.sb as sb


def get_loaded_match_ids(conn: duckdb.DuckDBPyConnection) -> set[int]:
    """Return the set of match_ids already loaded into raw_sb_lineups."""
    try:
        rows = conn.execute("SELECT DISTINCT match_id FROM raw_sb_lineups").fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()


def fetch_lineups(match_id: int) -> list[dict]:
    """Fetch lineups for one match and flatten both teams to a list of dicts."""
    lineup_dict = sb.lineups(match_id=match_id)
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_sb_lineups (
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

    conn.execute("DELETE FROM raw_sb_lineups WHERE match_id = ?", [match_id])

    if lineups:
        conn.executemany("""
            INSERT INTO raw_sb_lineups VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            [
                l["match_id"], l["team_name"], l["player_id"], l["player_name"],
                l["player_nickname"], l["jersey_number"], l["country_name"],
                l["ingested_at"],
            ]
            for l in lineups
        ])
        print(f"    Lineups: {len(lineups)} rows (match {match_id})")
