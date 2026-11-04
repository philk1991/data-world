#!/usr/bin/env python3
"""
NBA dataset ingestion script.

Downloads the core and extended box-score files and the play-by-play from the
Kaggle NBA dataset
(https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores)
and loads each into DuckDB. PlayByPlay.parquet (~0.9 GB, 18.8M events, 1996-97
onward) is the largest file and loads last.

Data is written to the shared DuckLake (see lake.py). All NBA tables
use the raw_nba schema to avoid collisions. Each file is a full-replace load, so
the script can be re-run safely to pick up the daily-updated upstream snapshot.

Configuration (via .env at the project root):
  KAGGLE_USERNAME — Kaggle account username (for kagglehub auth)
  KAGGLE_KEY      — Kaggle API key (create a token at https://www.kaggle.com/settings)
  LAKE_CATALOG / LAKE_DATA_PATH — the DuckLake to write to (see lake.py; defaults
                  work after `task lake:init`)

Usage (run from data-ingestion/):
    python ingest_nba.py
"""
from pathlib import Path
from dotenv import load_dotenv

from lake import connect_lake, lake_settings

from nba.ingestion.download import download_file
from nba.ingestion.load import load_file

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# Kaggle file → raw_nba table. The League Schedule files are omitted.
FILE_TABLE_MAP = {
    "Games.csv":                     "raw_nba_games",
    "PlayerStatistics.csv":          "raw_nba_player_statistics",
    "TeamStatistics.csv":            "raw_nba_team_statistics",
    "Players.csv":                   "raw_nba_players",
    "TeamHistories.csv":             "raw_nba_team_histories",
    "PlayerStatisticsExtended.csv":  "raw_nba_player_statistics_extended",
    "TeamStatisticsExtended.csv":    "raw_nba_team_statistics_extended",
    "PlayByPlay.parquet":            "raw_nba_play_by_play",
}


def main():
    print(f"Connecting to the lake ({lake_settings()[0]})\n")
    conn = connect_lake()

    loaded = 0
    total = len(FILE_TABLE_MAP)
    for i, (filename, table) in enumerate(FILE_TABLE_MAP.items(), start=1):
        print(f"[{i}/{total}] {filename}")
        path = download_file(filename)
        if path is None:
            continue
        load_file(conn, path, table)
        loaded += 1

    conn.close()
    print(f"\nDone. {loaded}/{total} files loaded into the lake")


if __name__ == "__main__":
    main()
