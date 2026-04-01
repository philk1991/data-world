"""
Fetch and load StatsBomb match metadata.

StatsBomb reference: sb.matches(competition_id, season_id) returns match
metadata for one competition/season. Called once per competition/season pair.

DuckDB table: raw_sb_matches
  Rows are replaced per (competition_id, season_id) on each run.

Many columns in the statsbombpy response are nested dicts (e.g. competition,
season, home_team, away_team). These are flattened during fetch.
"""
import duckdb
import pandas as pd
from datetime import datetime, timezone

import statsbombpy.sb as sb


def _safe_dict(val, key: str, default=None):
    """Extract a key from a dict column; return default if null or not a dict."""
    if isinstance(val, dict):
        return val.get(key, default)
    return default


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
        competition_stage = _safe_dict(row.get("competition_stage"), "name")
        stadium = _safe_dict(row.get("stadium"), "name")
        referee = _safe_dict(row.get("referee"), "name")

        records.append({
            "match_id":           int(row["match_id"]),
            "match_date":         str(row["match_date"]) if not pd.isna(row.get("match_date", None)) else None,
            "kick_off":           str(row["kick_off"]) if not pd.isna(row.get("kick_off", None)) else None,
            "competition_id":     int(_safe_dict(row.get("competition"), "competition_id", competition_id)),
            "competition_name":   str(_safe_dict(row.get("competition"), "competition_name", "")),
            "season_id":          int(_safe_dict(row.get("season"), "season_id", season_id)),
            "season_name":        str(_safe_dict(row.get("season"), "season_name", "")),
            "home_team_id":       int(_safe_dict(row.get("home_team"), "home_team_id", 0)),
            "home_team_name":     str(_safe_dict(row.get("home_team"), "home_team_name", "")),
            "away_team_id":       int(_safe_dict(row.get("away_team"), "away_team_id", 0)),
            "away_team_name":     str(_safe_dict(row.get("away_team"), "away_team_name", "")),
            "home_score":         int(row["home_score"]) if not pd.isna(row.get("home_score")) else None,
            "away_score":         int(row["away_score"]) if not pd.isna(row.get("away_score")) else None,
            "match_status":       str(row.get("match_status", "")),
            "match_week":         int(row["match_week"]) if not pd.isna(row.get("match_week")) else None,
            "competition_stage":  competition_stage,
            "stadium_name":       stadium,
            "referee_name":       referee,
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
            home_team_id        INTEGER,
            home_team_name      VARCHAR,
            away_team_id        INTEGER,
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            [
                m["match_id"], m["match_date"], m["kick_off"],
                m["competition_id"], m["competition_name"],
                m["season_id"], m["season_name"],
                m["home_team_id"], m["home_team_name"],
                m["away_team_id"], m["away_team_name"],
                m["home_score"], m["away_score"],
                m["match_status"], m["match_week"],
                m["competition_stage"], m["stadium_name"], m["referee_name"],
                m["ingested_at"],
            ]
            for m in matches
        ])
        print(f"  Loaded {len(matches)} matches "
              f"(competition {competition_id}, season {season_id})")
