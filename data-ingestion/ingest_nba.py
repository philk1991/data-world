#!/usr/bin/env python3
"""
NBA dataset ingestion script.

Downloads the core and extended box-score files from the Kaggle NBA dataset
(https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores)
and loads each into DuckDB. The large PlaybyPlay.parquet is intentionally skipped.

Data is written to the same DuckDB file as Spotify/StatsBomb data. All NBA tables
use the raw_nba schema to avoid collisions. Each file is a full-replace load, so
the script can be re-run safely to pick up the daily-updated upstream snapshot.

Configuration (via .env at the project root):
  KAGGLE_USERNAME — Kaggle account username (for kagglehub auth)
  KAGGLE_KEY      — Kaggle API key (create a token at https://www.kaggle.com/settings)
  DUCKDB_PATH     — path to the DuckDB file (shared with Spotify/StatsBomb ingest)

Usage (run from data-ingestion/):
    python ingest_nba.py
"""
import os
from pathlib import Path
import duckdb
from dotenv import load_dotenv

from nba.ingestion.download import download_file
from nba.ingestion.load import load_csv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "spotify.duckdb")

# Kaggle file → raw_nba table. PlaybyPlay.parquet and League Schedules are omitted.
FILE_TABLE_MAP = {
    "Games.csv":                     "raw_nba_games",
    "PlayerStatistics.csv":          "raw_nba_player_statistics",
    "TeamStatistics.csv":            "raw_nba_team_statistics",
    "Players.csv":                   "raw_nba_players",
    "TeamHistories.csv":             "raw_nba_team_histories",
    "PlayerStatisticsExtended.csv":  "raw_nba_player_statistics_extended",
    "TeamStatisticsExtended.csv":    "raw_nba_team_statistics_extended",
}


def main():
    db_path = os.environ.get("DUCKDB_PATH", _DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    print(f"Connecting to {db_path}\n")
    conn = duckdb.connect(db_path)

    loaded = 0
    total = len(FILE_TABLE_MAP)
    for i, (filename, table) in enumerate(FILE_TABLE_MAP.items(), start=1):
        print(f"[{i}/{total}] {filename}")
        path = download_file(filename)
        if path is None:
            continue
        load_csv(conn, path, table)
        loaded += 1

    conn.close()
    print(f"\nDone. {loaded}/{total} files loaded into {db_path}")


if __name__ == "__main__":
    main()
