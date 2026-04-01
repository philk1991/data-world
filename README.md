# data-world

A local data platform for ingesting personal Spotify data into DuckDB, transforming it with dbt, and visualising it in a SvelteKit dashboard.

## Architecture

```
data-world/
├── data-ingestion/        # Python pipeline — pulls from Spotify API → DuckDB
│   ├── ingest.py          # Entry point
│   └── spotify/
│       ├── auth.py        # OAuth via Spotipy (token cached in .spotify_cache)
│       └── ingestion/
│           ├── top_artists.py      # Top 50 artists × 3 time ranges
│           ├── top_tracks.py       # Top 50 tracks × 3 time ranges
│           └── recently_played.py  # Last 50 played tracks
├── dbt/                   # Transformation layer
│   ├── models/
│   │   ├── staging/       # Cleaned views over raw tables
│   │   └── marts/         # Analysis-ready tables used by the dashboard
│   └── profiles.yml       # Points dbt at the local DuckDB file
├── dashboard/             # SvelteKit web app — visualises the data
├── data/                  # DuckDB database file — gitignored
├── Taskfile.yml           # Task runner
└── requirements.txt       # Python dependencies
```

### How data flows

```
Spotify API
    │
    ▼
data-ingestion/ingest.py
    │  writes raw_* tables
    ▼
data/spotify.duckdb
    │
    ▼
dbt (staging views → mart tables)
    │  stg_top_artists, stg_top_tracks, stg_recently_played
    │  top_artists_by_period, top_tracks_by_period
    ▼
dashboard/ (SvelteKit SSR)
    │  reads via duckdb npm package (READ_ONLY)
    ▼
http://localhost:5173
```

## Data Sources

All data comes from the [Spotify Web API](https://developer.spotify.com/documentation/web-api) using your personal account.

| Endpoint | Raw Table | Description |
|---|---|---|
| `/me/top/artists` | `raw_top_artists` | Top 50 artists across short, medium, and long term |
| `/me/top/tracks` | `raw_top_tracks` | Top 50 tracks across short, medium, and long term |
| `/me/player/recently-played` | `raw_recently_played` | Last 50 played tracks with timestamps |

> The Spotify Audio Features and Recommendations endpoints are deprecated for new apps and are not included.

## dbt Models

### Staging (views)
| Model | Source | Description |
|---|---|---|
| `stg_top_artists` | `raw_top_artists` | Typed artists with time range and rank |
| `stg_top_tracks` | `raw_top_tracks` | Typed tracks; album dates normalised to `YYYY-MM-DD` |
| `stg_recently_played` | `raw_recently_played` | Play events with derived `played_date` and `played_hour` |

### Marts (tables)
| Model | Description |
|---|---|
| `top_artists_by_period` | One row per artist with `rank_short_term`, `rank_medium_term`, `rank_long_term` columns |
| `top_tracks_by_period` | One row per track with the same three rank columns |

Each mart is a pivot of the three time ranges into a single row per entity — the dashboard filters client-side based on which period tab is selected.

## Setup

### Prerequisites
- Python 3.12
- Node.js 22 LTS (`brew install node@22`)
- [Task](https://taskfile.dev) (`brew install go-task`)
- A [Spotify Developer app](https://developer.spotify.com/dashboard) with `http://127.0.0.1:8888/callback` as a Redirect URI

### Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the project root:

```bash
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
DUCKDB_PATH=/absolute/path/to/data-world/data/spotify.duckdb
```

> `DUCKDB_PATH` must be an absolute path. A relative path will resolve differently depending on which directory the script is run from.

### Dashboard

```bash
task dashboard:install
```

## Usage

All commands run from the root of `data-world/` using [Task](https://taskfile.dev).

### Ingest

| Command | Description |
|---|---|
| `task ingest` | Clear Spotify cache and run the full ingest pipeline (triggers browser auth) |
| `task ingest:no-cache-clear` | Run ingest using the existing cached token |

On first run, a browser tab will open to authorise with Spotify. The token is cached in `.spotify_cache` and refreshed automatically on subsequent runs.

### dbt

| Command | Description |
|---|---|
| `task dbt:run` | Run all models |
| `task dbt:test` | Run all tests |
| `task dbt:build` | Run all models then test them |
| `task dbt:compile` | Validate SQL without executing |
| `task dbt:docs` | Generate and serve dbt docs in the browser |
| `task dbt:run:select MODEL=<name>` | Run a specific model |
| `task dbt:test:select MODEL=<name>` | Test a specific model |

### Dashboard

| Command | Description |
|---|---|
| `task dashboard:dev` | Start dashboard with hot reload at http://localhost:5173 |
| `task dashboard:build` | Build for production |
| `task dashboard:start` | Serve the production build |

### Full refresh

```bash
task refresh
```

Runs `ingest` → `dbt:build` in sequence.

## Important: DuckDB version alignment

The Python (`duckdb==1.2.1`) and Node.js (`duckdb@1.2.1`) packages must use the **same version**. A mismatch causes the newer version to attempt a file format migration when it opens the database, requiring exclusive write access — which conflicts with dbt. Both are pinned to `1.2.1`.

## Viewing Data Directly

- **DBeaver** — New connection → DuckDB → path: `<absolute path>/data/spotify.duckdb` (use Read-Only mode to avoid write lock conflicts with dbt)
- **DuckDB CLI** — `python -m duckdb data/spotify.duckdb`
- **Harlequin** (TUI) — `pip install harlequin && harlequin data/spotify.duckdb`
