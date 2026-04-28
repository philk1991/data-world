"""
Fetch and load StatsBomb competition/season pairs.

StatsBomb reference: sb.competitions() returns all available competition/season
combinations in the open data set — roughly 100 rows covering domestic leagues,
international tournaments, and women's competitions.

DuckDB table: raw_sb_competitions
  Full replace on each run (small table, ~100 rows).
"""
import duckdb
from datetime import datetime, timezone

import statsbombpy.sb as sb


def fetch_competitions() -> list[dict]:
    """Return all available StatsBomb competitions as a list of flat dicts."""
    df = sb.competitions()
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for _, row in df.iterrows():
        records.append({
            "competition_id":           int(row["competition_id"]),
            "competition_name":         str(row["competition_name"]),
            "country_name":             str(row["country_name"]),
            "competition_gender":       str(row["competition_gender"]),
            "competition_youth":        bool(row.get("competition_youth", False)),
            "competition_international": bool(row.get("competition_international", False)),
            "season_id":                int(row["season_id"]),
            "season_name":              str(row["season_name"]),
            "match_available_360":      bool(row.get("match_available_360", False)),
            "ingested_at":              now,
        })
    return records


def load_competitions(conn: duckdb.DuckDBPyConnection, competitions: list[dict]) -> None:
    """Replace all competition rows in DuckDB.

    Creates the table if it doesn't exist, clears all rows, then bulk-inserts.
    Full replace is safe because the competition list is small and static.
    """
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_statsbomb")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_statsbomb.raw_sb_competitions (
            competition_id            INTEGER,
            competition_name          VARCHAR,
            country_name              VARCHAR,
            competition_gender        VARCHAR,
            competition_youth         BOOLEAN,
            competition_international BOOLEAN,
            season_id                 INTEGER,
            season_name               VARCHAR,
            match_available_360       BOOLEAN,
            ingested_at               TIMESTAMPTZ
        )
    """)

    conn.execute("DELETE FROM raw_statsbomb.raw_sb_competitions")

    if competitions:
        conn.executemany("""
            INSERT INTO raw_statsbomb.raw_sb_competitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            [
                c["competition_id"], c["competition_name"], c["country_name"],
                c["competition_gender"], c["competition_youth"], c["competition_international"],
                c["season_id"], c["season_name"], c["match_available_360"], c["ingested_at"],
            ]
            for c in competitions
        ])
        print(f"  Loaded {len(competitions)} competition/season pairs")
