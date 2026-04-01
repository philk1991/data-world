"""
Fetch and load StatsBomb match metadata.

StatsBomb reference: sb.matches(competition_id, season_id) returns match
metadata for one competition/season. Called once per competition/season pair.

DuckDB table: raw_sb_matches
  Rows are replaced per (competition_id, season_id) on each run.

statsbombpy already flattens all nested fields — competition, season,
home_team, away_team, stadium, referee, and competition_stage are all plain
strings. IDs for competition and season are taken from the function arguments
since statsbombpy does not expose them as separate columns.
"""
import duckdb
import pandas as pd
from datetime import datetime, timezone

import statsbombpy.sb as sb


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


def fetch_matches(competition_id: int, season_id: int) -> list[dict]:
    """Fetch match metadata for one competition/season."""
    try:
        df = sb.matches(competition_id=competition_id, season_id=season_id)
    except Exception as e:
        print(f"  Warning: could not fetch matches for competition {competition_id} "
              f"season {season_id}: {e}")
        return []

    now = datetime.now(timezone.utc).isoformat()
    records = []
    for _, row in df.iterrows():
        records.append({
            "match_id":           int(row["match_id"]),
            "match_date":         _str_or_none(row.get("match_date")),
            "kick_off":           _str_or_none(row.get("kick_off")),
            "competition_id":     competition_id,
            "competition_name":   _str_or_none(row.get("competition")),
            "season_id":          season_id,
            "season_name":        _str_or_none(row.get("season")),
            "home_team_id":       None,
            "home_team_name":     _str_or_none(row.get("home_team")),
            "away_team_id":       None,
            "away_team_name":     _str_or_none(row.get("away_team")),
            "home_score":         int(row["home_score"]) if not pd.isna(row.get("home_score")) else None,
            "away_score":         int(row["away_score"]) if not pd.isna(row.get("away_score")) else None,
            "match_status":       _str_or_none(row.get("match_status")),
            "match_week":         int(row["match_week"]) if not pd.isna(row.get("match_week")) else None,
            "competition_stage":  _str_or_none(row.get("competition_stage")),
            "stadium_name":       _str_or_none(row.get("stadium")),
            "referee_name":       _str_or_none(row.get("referee")),
            "ingested_at":        now,
        })
    return records


def load_matches(
    conn: duckdb.DuckDBPyConnection,
    matches: list[dict],
    competition_id: int,
    season_id: int,
) -> None:
    """Replace match rows for one competition/season.

    Deletes existing rows for the (competition_id, season_id) pair before
    inserting, so re-runs are idempotent.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_sb_matches (
            match_id            INTEGER,
            match_date          VARCHAR,
            kick_off            VARCHAR,
            competition_id      INTEGER,
            competition_name    VARCHAR,
            season_id           INTEGER,
            season_name         VARCHAR,
            home_team_name      VARCHAR,
            away_team_name      VARCHAR,
            home_score          INTEGER,
            away_score          INTEGER,
            match_status        VARCHAR,
            match_week          INTEGER,
            competition_stage   VARCHAR,
            stadium_name        VARCHAR,
            referee_name        VARCHAR,
            ingested_at         TIMESTAMPTZ
        )
    """)

    conn.execute(
        "DELETE FROM raw_sb_matches WHERE competition_id = ? AND season_id = ?",
        [competition_id, season_id],
    )

    if matches:
        conn.executemany("""
            INSERT INTO raw_sb_matches VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            [
                m["match_id"], m["match_date"], m["kick_off"],
                m["competition_id"], m["competition_name"],
                m["season_id"], m["season_name"],
                m["home_team_name"],
                m["away_team_name"],
                m["home_score"], m["away_score"],
                m["match_status"], m["match_week"],
                m["competition_stage"], m["stadium_name"], m["referee_name"],
                m["ingested_at"],
            ]
            for m in matches
        ])
        print(f"  Loaded {len(matches)} matches "
              f"(competition {competition_id}, season {season_id})")
