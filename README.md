# data-world

A local data platform for ingesting personal Spotify data and StatsBomb open football data into DuckDB, transforming it with dbt, and visualising it in a SvelteKit dashboard.

## Architecture

```
data-world/
├── data-ingestion/        # Python pipelines — pulls from external sources → DuckDB
│   ├── ingest.py          # Spotify entry point
│   ├── ingest_statsbomb.py # StatsBomb entry point
│   ├── spotify/
│   │   ├── auth.py        # OAuth via Spotipy (token cached in .spotify_cache)
│   │   └── ingestion/
│   │       ├── top_artists.py      # Top 50 artists × 3 time ranges
│   │       ├── top_tracks.py       # Top 50 tracks × 3 time ranges
│   │       └── recently_played.py  # Last 50 played tracks
│   └── statsbomb/
│       └── ingestion/
│           ├── competitions.py     # All competition/season pairs
│           ├── matches.py          # Match metadata per competition/season
│           ├── events.py           # Match events (incremental)
│           └── lineups.py          # Player lineups (incremental)
├── dbt/                   # Transformation layer
│   ├── models/
│   │   ├── staging/       # Cleaned views over raw tables
│   │   └── marts/         # Analysis-ready tables
│   └── profiles.yml       # Points dbt at the local DuckDB file
├── dashboard/             # SvelteKit web app — visualises Spotify data
├── data/                  # DuckDB database file — gitignored
├── Taskfile.yml           # Task runner
└── requirements.txt       # Python dependencies
```

### How data flows

```
Spotify API                    StatsBomb open data (GitHub)
    │                                   │
    ▼                                   ▼
ingest.py                      ingest_statsbomb.py
    │  raw_top_artists                  │  raw_sb_competitions
    │  raw_top_tracks                   │  raw_sb_matches
    │  raw_recently_played              │  raw_sb_events
    └──────────────┬───────────────────┘  raw_sb_lineups
                   ▼
           data/spotify.duckdb
                   │
                   ▼
            dbt build
       (staging views → mart tables)
                   │
                   ▼
           dashboard/ (SvelteKit SSR)
        reads via duckdb npm (READ_ONLY)
                   ▼
          http://localhost:5173
```

## Data Sources

### Spotify

Personal listening data pulled from the [Spotify Web API](https://developer.spotify.com/documentation/web-api). Requires a Spotify Developer app and OAuth authentication.

| Endpoint | Raw Table | Description |
|---|---|---|
| `/me/top/artists` | `raw_top_artists` | Top 50 artists across short, medium, and long term |
| `/me/top/tracks` | `raw_top_tracks` | Top 50 tracks across short, medium, and long term |
| `/me/player/recently-played` | `raw_recently_played` | Last 50 played tracks with timestamps |

> The Audio Features and Recommendations endpoints are deprecated for new apps and are not included.

### StatsBomb

Free, open football event data from [StatsBomb open data](https://github.com/statsbomb/open-data). No authentication required — data is fetched from GitHub via the `statsbombpy` library.

| Dataset | Raw Table | Description |
|---|---|---|
| Competitions | `raw_sb_competitions` | All available competition/season pairs (~75 competitions) |
| Matches | `raw_sb_matches` | Match metadata for every competition/season |
| Events | `raw_sb_events` | Every on-ball action in every match (Pass, Shot, Dribble, Carry, Pressure, etc.) |
| Lineups | `raw_sb_lineups` | Player rosters for each match |

Covers La Liga, Premier League, Bundesliga, Ligue 1, Serie A, FIFA World Cup (1958–2022), UEFA Euro (2020, 2024), Women's competitions, and more. Events data is ingested **incrementally** — re-running skips matches already in the database.

## dbt Models

### Staging (views)

| Model | Source | Description |
|---|---|---|
| `stg_top_artists` | `raw_top_artists` | Typed artists with time range and rank |
| `stg_top_tracks` | `raw_top_tracks` | Typed tracks; album dates normalised to `YYYY-MM-DD` |
| `stg_recently_played` | `raw_recently_played` | Play events with derived `played_date` and `played_hour` |
| `stg_sb_competitions` | `raw_sb_competitions` | Competition/season pairs with typed columns |
| `stg_sb_matches` | `raw_sb_matches` | Matches filtered to available; derives `match_result` and `goal_difference` |
| `stg_sb_events` | `raw_sb_events` | Events with derived `seconds_elapsed`; location x/y pre-parsed |
| `stg_sb_lineups` | `raw_sb_lineups` | Player lineup rows with typed columns |

### Marts (tables)

| Model | Description |
|---|---|
| `top_artists_by_period` | One row per artist with `rank_short_term`, `rank_medium_term`, `rank_long_term` |
| `top_tracks_by_period` | One row per track with the same three rank columns |
| `sb_match_summary` | One row per match with competition context and aggregate event counts (shots, passes, dribbles, etc.) |
| `sb_player_stats` | One row per (player, team) with aggregate stats across all matches |

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

```
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
| `task ingest` | Clear Spotify cache and run the full Spotify ingest (triggers browser auth) |
| `task ingest:no-cache-clear` | Run Spotify ingest using the existing cached token |
| `task ingest:statsbomb` | Run the StatsBomb ingest (incremental — skips already-loaded matches) |

On first run, `task ingest` opens a browser tab to authorise with Spotify. The token is cached in `.spotify_cache` and refreshed automatically on subsequent runs. StatsBomb requires no authentication.

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

### Refresh

| Command | Description |
|---|---|
| `task refresh` | Spotify ingest → `dbt:build` |
| `task refresh:statsbomb` | StatsBomb ingest → `dbt:build` |
| `task refresh:all` | Spotify + StatsBomb ingest → `dbt:build` |

## Important: DuckDB version alignment

The Python (`duckdb==1.2.1`) and Node.js (`duckdb@1.2.1`) packages must use the **same version**. A mismatch causes the newer version to attempt a file format migration when it opens the database, requiring exclusive write access — which conflicts with dbt. Both are pinned to `1.2.1`.

## Viewing Data Directly

- **DBeaver** — New connection → DuckDB → path: `<absolute path>/data/spotify.duckdb` (use Read-Only mode to avoid write lock conflicts with dbt)
- **DuckDB CLI** — `python -m duckdb data/spotify.duckdb`
- **Harlequin** (TUI) — `pip install harlequin && harlequin data/spotify.duckdb`
