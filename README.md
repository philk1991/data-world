# data-world

A local data platform for ingesting personal Spotify data into DuckDB and transforming it with dbt.

## Overview

```
data-world/
├── data-ingestion/        # Python ingestion pipeline
│   ├── ingest.py          # Entry point — run this to pull data from Spotify
│   └── spotify/
│       ├── auth.py        # OAuth authentication via Spotipy
│       └── ingestion/
│           ├── top_artists.py     # Top 50 artists × 3 time ranges
│           ├── top_tracks.py      # Top 50 tracks × 3 time ranges
│           └── recently_played.py # Last 50 played tracks
├── dbt/                   # dbt transformation layer
│   ├── models/
│   │   ├── staging/       # Cleaned views over raw tables
│   │   └── marts/         # Analysis-ready tables
│   └── profiles.yml       # Points dbt at the local DuckDB file
├── data/                  # DuckDB database file (gitignored)
├── Taskfile.yml           # Task runner — see commands below
└── requirements.txt       # Python dependencies
```

## Data Sources

All data is pulled from the [Spotify Web API](https://developer.spotify.com/documentation/web-api) using your personal account.

| Endpoint | Table | Description |
|---|---|---|
| `/me/top/artists` | `raw_top_artists` | Top 50 artists across short, medium, and long term |
| `/me/top/tracks` | `raw_top_tracks` | Top 50 tracks across short, medium, and long term |
| `/me/player/recently-played` | `raw_recently_played` | Last 50 played tracks with timestamps |

> **Note:** The Spotify Audio Features and Recommendations endpoints are deprecated for new apps and are not included.

## dbt Models

### Staging (views)
| Model | Description |
|---|---|
| `stg_top_artists` | Cleaned artists with time range and rank |
| `stg_top_tracks` | Cleaned tracks, album dates normalised to full dates |
| `stg_recently_played` | Play events with derived `played_date` and `played_hour` |

### Marts (tables)
| Model | Description |
|---|---|
| `top_artists_by_period` | One row per artist, ranked across all three time periods |
| `top_tracks_by_period` | One row per track, ranked across all three time periods |

## Setup

### Prerequisites
- Python 3.12
- A [Spotify Developer app](https://developer.spotify.com/dashboard) with `http://127.0.0.1:8888/callback` added as a Redirect URI

### Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in your Spotify credentials:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

## Usage

All commands are run from the root of `data-world/` using [Task](https://taskfile.dev).

| Command | Description |
|---|---|
| `task ingest` | Clear Spotify cache and run the full ingest pipeline |
| `task ingest:no-cache-clear` | Run ingest using the existing cached token |
| `task dbt:run` | Run all dbt models |
| `task dbt:test` | Run all dbt tests |
| `task dbt:build` | Run all models then test them |
| `task dbt:compile` | Validate SQL without executing |
| `task dbt:docs` | Generate and serve dbt docs in the browser |
| `task dbt:run:select MODEL=<name>` | Run a specific model |
| `task dbt:test:select MODEL=<name>` | Test a specific model |
| `task refresh` | Full end-to-end: ingest → build → test |

On first run, `task ingest` will open a browser tab to authorise with Spotify. The token is cached locally in `.spotify_cache` and refreshed automatically on subsequent runs.

## Viewing Data

The DuckDB database is written to `data/spotify.duckdb`. Connect with:

- **DBeaver** — New connection → DuckDB → path: `<absolute path>/data/spotify.duckdb`
- **DuckDB CLI** — `python -m duckdb data/spotify.duckdb`
- **Harlequin** (TUI) — `pip install harlequin && harlequin data/spotify.duckdb`

> When running dbt, close any active DBeaver connection first — DuckDB only allows one writer at a time. Set the DBeaver connection to read-only mode to avoid this.
