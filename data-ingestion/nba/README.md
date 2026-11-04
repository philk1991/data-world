# NBA ingestion

Batch ingestion of historical NBA box scores and play-by-play from the
[Kaggle NBA dataset (eoinamoore)](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores).

## Source & auth

Requires Kaggle API credentials. Create a token at
[kaggle.com/settings](https://www.kaggle.com/settings) → "Create New Token" and set
`KAGGLE_USERNAME` / `KAGGLE_KEY` in the project-root `.env`. `kagglehub` reads these
automatically (or falls back to `~/.kaggle/kaggle.json`).

## What it does

`ingest_nba.py` downloads the **core + extended** box-score files and the play-by-play one
at a time and loads each into DuckDB as a full-replace table (`read_csv_auto` for the CSVs,
`read_parquet` for `PlayByPlay.parquet`, ~0.9 GB and 18.8M events from 1996-97 on). The
League Schedule files are intentionally skipped. Re-running
rebuilds every table from the latest daily snapshot, so the script is idempotent.

| Kaggle file | DuckDB table |
|---|---|
| `Games.csv` | `raw_nba.raw_nba_games` |
| `PlayerStatistics.csv` | `raw_nba.raw_nba_player_statistics` |
| `TeamStatistics.csv` | `raw_nba.raw_nba_team_statistics` |
| `Players.csv` | `raw_nba.raw_nba_players` |
| `TeamHistories.csv` | `raw_nba.raw_nba_team_histories` |
| `PlayerStatisticsExtended.csv` | `raw_nba.raw_nba_player_statistics_extended` |
| `TeamStatisticsExtended.csv` | `raw_nba.raw_nba_team_statistics_extended` |
| `PlayByPlay.parquet` | `raw_nba.raw_nba_play_by_play` |

| Entry point | Destination | Task command |
|---|---|---|
| `data-ingestion/ingest_nba.py` | lake → `raw_nba.*` | `task ingest:nba` |
