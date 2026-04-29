# data-world

A local data platform demonstrating multiple ingestion patterns — batch API pulls, open dataset loading, and real-time streaming — all flowing through DuckDB, transformed with dbt, and visualised in SvelteKit dashboards.

## Project structure

```
data-world/
├── data-ingestion/            # Python ingestion pipelines
│   ├── ingest.py              # Spotify entry point
│   ├── ingest_statsbomb.py    # StatsBomb entry point
│   ├── spotify/               # OAuth + API fetch logic
│   ├── statsbomb/             # GitHub fetch logic
│   └── crypto/                # Binance WebSocket → Kafka
│       ├── producer.py        # WebSocket → Kafka topic
│       └── consumer.py        # Kafka → DuckDB + live JSON sidecar
├── dbt/                       # Transformation layer (all sources)
│   ├── models/
│   │   ├── staging/
│   │   │   ├── spotify/       # Cleaned views over raw Spotify tables
│   │   │   ├── statsbomb/     # Cleaned views over raw StatsBomb tables
│   │   │   └── crypto/        # Cleaned views over raw trade ticks
│   │   └── marts/
│   │       ├── spotify/       # Analysis-ready Spotify tables
│   │       ├── statsbomb/     # Analysis-ready football tables
│   │       └── crypto/        # Incremental OHLCV candle tables
│   ├── macros/                # generate_schema_name override
│   └── profiles.yml           # DuckDB connection + crypto_raw attach
├── dashboards/
│   ├── spotify/               # SvelteKit app — Spotify listening data
│   └── crypto/                # SvelteKit app — real-time trade feed
├── data/                      # DuckDB files + live JSON sidecar (gitignored)
│   ├── spotify.duckdb         # Spotify + StatsBomb data
│   ├── crypto_raw.duckdb      # Raw crypto trades (consumer-owned)
│   └── live_data.json         # Atomic JSON sidecar written by consumer
├── scripts/                   # One-off utility scripts
├── Taskfile.yml               # Task runner
└── requirements.txt           # Python dependencies
```

## Architecture

### Batch pipelines (Spotify + StatsBomb)

```
Spotify API                    StatsBomb open data (GitHub)
    │                                   │
    ▼                                   ▼
ingest.py                      ingest_statsbomb.py
    │  raw_spotify.*                    │  raw_statsbomb.*
    └──────────────┬───────────────────┘
                   ▼
          data/spotify.duckdb
                   │
                   ▼
            dbt build
    (staging_spotify / staging_statsbomb → marts)
                   │
                   ▼
        dashboards/spotify (SvelteKit SSR)
          reads via duckdb npm (READ_ONLY)
                   ▼
          http://localhost:5173
```

### Streaming pipeline (Crypto)

```
Binance public WebSocket
    │  BTC/USDT, ETH/USDT trade ticks
    ▼
crypto/producer.py
    │  publishes JSON to 'crypto.trades' Kafka topic
    ▼
Kafka (localhost:9092)
    │
    ▼
crypto/consumer.py
    ├──▶ data/crypto_raw.duckdb   (raw_crypto.raw_trades — append only)
    └──▶ data/live_data.json      (atomic overwrite after each batch)
                                           │
                                           ▼
                               dashboards/crypto (SvelteKit)
                                 reads live_data.json via API route
                                           ▼
                                 http://localhost:5174

dbt build (run separately, read-only attach to crypto_raw.duckdb)
    └──▶ staging_crypto.stg_crypto_trades
    └──▶ marts.ohlcv_1m / ohlcv_1h  (incremental OHLCV candles)
```

> The crypto dashboard reads `live_data.json` rather than querying DuckDB directly.
> This avoids write-lock conflicts between the consumer and the dashboard.

## Data sources

### Spotify

Personal listening data from the [Spotify Web API](https://developer.spotify.com/documentation/web-api). Requires a Spotify Developer app and OAuth.

| Endpoint | Schema.Table | Description |
|---|---|---|
| `/me/top/artists` | `raw_spotify.raw_top_artists` | Top 50 artists × 3 time ranges |
| `/me/top/tracks` | `raw_spotify.raw_top_tracks` | Top 50 tracks × 3 time ranges |
| `/me/player/recently-played` | `raw_spotify.raw_recently_played` | Last 50 played tracks with timestamps |

### StatsBomb

Free open football event data from [StatsBomb open data](https://github.com/statsbomb/open-data). No authentication required.

| Dataset | Schema.Table | Description |
|---|---|---|
| Competitions | `raw_statsbomb.raw_sb_competitions` | All available competition/season pairs |
| Matches | `raw_statsbomb.raw_sb_matches` | Match metadata per competition/season |
| Events | `raw_statsbomb.raw_sb_events` | Every on-ball action per match (incremental) |
| Lineups | `raw_statsbomb.raw_sb_lineups` | Player rosters per match (incremental) |

### Crypto (Binance)

Real-time trade ticks streamed from [Binance public WebSocket API](https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams). No authentication required.

| Symbol | Schema.Table | Description |
|---|---|---|
| BTC/USDT | `raw_crypto.raw_trades` | Every executed trade tick (append-only) |
| ETH/USDT | `raw_crypto.raw_trades` | Every executed trade tick (append-only) |

## dbt models

All models live in `dbt/` and target `data/spotify.duckdb` as the primary database, with `data/crypto_raw.duckdb` attached read-only as `crypto_raw`.

### Staging (views)

| Model | Schema | Description |
|---|---|---|
| `stg_top_artists` | `staging_spotify` | Typed artists with time range and rank |
| `stg_top_tracks` | `staging_spotify` | Typed tracks; album dates normalised |
| `stg_recently_played` | `staging_spotify` | Play events with `played_date` and `played_hour` |
| `stg_sb_competitions` | `staging_statsbomb` | Competition/season pairs |
| `stg_sb_matches` | `staging_statsbomb` | Matches with derived `match_result` and `goal_difference` |
| `stg_sb_events` | `staging_statsbomb` | Events with `seconds_elapsed`; location x/y pre-parsed |
| `stg_sb_lineups` | `staging_statsbomb` | Player lineup rows |
| `stg_crypto_trades` | `staging_crypto` | Typed trade ticks with `notional_value` |

### Marts (tables)

| Model | Schema | Description |
|---|---|---|
| `top_artists_by_period` | `marts` | One row per artist with rank across all three time ranges |
| `top_tracks_by_period` | `marts` | One row per track with rank across all three time ranges |
| `sb_match_summary` | `marts` | One row per match with aggregate event counts |
| `sb_player_stats` | `marts` | One row per (player, team) with aggregate stats |
| `ohlcv_1m` | `marts` | 1-minute OHLCV candles per trading pair (incremental) |
| `ohlcv_1h` | `marts` | 1-hour OHLCV candles per trading pair (incremental) |

## Setup

### Prerequisites

- Python 3.12
- Node.js 22 LTS — `brew install node@22`
- [Task](https://taskfile.dev) — `brew install go-task`
- Kafka — `brew install kafka`
- A [Spotify Developer app](https://developer.spotify.com/dashboard) with `http://127.0.0.1:8888/callback` as a Redirect URI

### Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Kafka

```bash
# Start ZooKeeper and Kafka (runs in background as launchd services)
brew services start zookeeper
brew services start kafka

# Create the topic (only needed once)
kafka-topics --create --topic crypto.trades --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

### Configure

Create a `.env` file in the project root:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback

DUCKDB_PATH=/absolute/path/to/data-world/data/spotify.duckdb
CRYPTO_DB_PATH=/absolute/path/to/data-world/data/crypto_raw.duckdb
```

> Both `DUCKDB_PATH` and `CRYPTO_DB_PATH` must be absolute paths.

### Dashboard dependencies

```bash
task dashboard:install
task dashboard:crypto:install
```

## Usage

All commands run from the root of `data-world/` using [Task](https://taskfile.dev).

### Ingest

| Command | Description |
|---|---|
| `task ingest` | Clear Spotify cache and run the full Spotify ingest (triggers browser auth on first run) |
| `task ingest:no-cache-clear` | Run Spotify ingest using the existing cached token |
| `task ingest:statsbomb` | Run the StatsBomb ingest (incremental — skips already-loaded matches) |

### Crypto streaming

Start both processes in separate terminals:

```bash
task crypto:producer   # Binance WebSocket → Kafka
task crypto:consumer   # Kafka → DuckDB + live_data.json
```

| Command | Description |
|---|---|
| `task crypto:producer` | Stream BTC/USDT and ETH/USDT ticks from Binance into Kafka |
| `task crypto:consumer` | Consume from Kafka, write to DuckDB, and update the live JSON sidecar |

### dbt

| Command | Description |
|---|---|
| `task dbt:run` | Run all models (all sources) |
| `task dbt:test` | Run all tests |
| `task dbt:build` | Run all models then test them |
| `task dbt:compile` | Validate SQL without executing |
| `task dbt:docs` | Generate and serve dbt docs in the browser |
| `task dbt:run:select MODEL=<name>` | Run a specific model |
| `task dbt:test:select MODEL=<name>` | Test a specific model |
| `task dbt:crypto:build` | Run and test crypto models only |

### Dashboards

| Command | Description |
|---|---|
| `task dashboard:dev` | Start Spotify dashboard at http://localhost:5173 |
| `task dashboard:build` | Build Spotify dashboard for production |
| `task dashboard:crypto:dev` | Start crypto dashboard at http://localhost:5174 |
| `task dashboard:crypto:build` | Build crypto dashboard for production |

### Full refresh

| Command | Description |
|---|---|
| `task refresh` | Spotify ingest → `dbt:build` |
| `task refresh:statsbomb` | StatsBomb ingest → `dbt:build` |
| `task refresh:all` | Spotify + StatsBomb ingest → `dbt:build` |

## Viewing data directly

- **DBeaver** — connect to `data/spotify.duckdb` or `data/crypto_raw.duckdb` in Read-Only mode
- **DuckDB CLI** — `duckdb data/spotify.duckdb` or `duckdb data/crypto_raw.duckdb`
- **Harlequin** (TUI) — `pip install harlequin && harlequin data/spotify.duckdb`

> Open `crypto_raw.duckdb` in read-only mode when the consumer is running to avoid lock conflicts.

## DuckDB version alignment

The Python (`duckdb==1.2.1`) and Node.js (`duckdb@1.2.1`) packages must use the **same version**. A mismatch causes the newer version to attempt a file format migration requiring exclusive write access, which conflicts with other processes. Both are pinned to `1.2.1`.
