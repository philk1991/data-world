#!/usr/bin/env python3
"""
Migrate existing DuckDB tables from the main schema into source-specific schemas.

Before:  main.raw_top_artists, main.raw_sb_events, etc.
After:   raw_spotify.raw_top_artists, raw_statsbomb.raw_sb_events, etc.

Run once after upgrading to the new schema convention. Old tables in main are
preserved — verify the migration first, then drop them manually if desired.

Usage (run from project root):
    python scripts/migrate_schemas.py
"""
import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "spotify.duckdb")

SPOTIFY_TABLES = ["raw_top_artists", "raw_top_tracks", "raw_recently_played"]
STATSBOMB_TABLES = ["raw_sb_competitions", "raw_sb_matches", "raw_sb_events", "raw_sb_lineups"]


def migrate(conn: duckdb.DuckDBPyConnection, tables: list[str], target_schema: str) -> None:
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {target_schema}")
    for table in tables:
        conn.execute(f"CREATE OR REPLACE TABLE {target_schema}.{table} AS SELECT * FROM main.{table}")
        count = conn.execute(f"SELECT count(*) FROM {target_schema}.{table}").fetchone()[0]
        print(f"  {target_schema}.{table}: {count:,} rows")


def main() -> None:
    db_path = os.environ.get("DUCKDB_PATH", _DEFAULT_DB_PATH)
    print(f"Connecting to {db_path}\n")
    conn = duckdb.connect(db_path)

    print("Migrating Spotify tables → raw_spotify...")
    migrate(conn, SPOTIFY_TABLES, "raw_spotify")

    print("\nMigrating StatsBomb tables → raw_statsbomb...")
    migrate(conn, STATSBOMB_TABLES, "raw_statsbomb")

    conn.close()
    print("\nMigration complete.")
    print("Old tables in main are preserved. Drop manually once verified:")
    for t in SPOTIFY_TABLES + STATSBOMB_TABLES:
        print(f"  DROP TABLE IF EXISTS main.{t};")


if __name__ == "__main__":
    main()
