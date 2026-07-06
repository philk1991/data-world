# data-world

A local data platform demonstrating multiple ingestion patterns — batch API pulls, open dataset loading, and real-time streaming — all flowing through DuckDB, transformed with dbt, and visualised in SvelteKit dashboards.

## Project structure

```
data-world/
├── data-ingestion/            # Python ingestion pipelines
│   ├── ingest.py              # Spotify entry point
│   ├── ingest_statsbomb.py    # StatsBomb entry point
│   ├── ingest_nba.py          # NBA entry point (Kaggle bulk dataset)
│   ├── ingest_openf1.py       # OpenF1 entry point
│   ├── spotify/               # OAuth + API fetch logic
│   ├── statsbomb/             # GitHub fetch logic
│   ├── nba/                   # kagglehub download + full-replace load
│   ├── openf1/                # OpenF1 fetch logic (rate-limit backoff)
│   ├── crypto/                # Binance WebSocket → Kafka
│   │   ├── producer.py        # WebSocket → Kafka topic
│   │   └── consumer.py        # Kafka → DuckDB + live JSON sidecar
│   └── payments/              # Synthetic payments → Kafka (practice build)
│       ├── producer.py        # Synthetic events → two Kafka topics
│       └── consumer.py        # Kafka → DuckDB (requests + late rejections)
├── dbt/                       # Transformation layer (all sources)
│   ├── models/
│   │   ├── staging/
│   │   │   ├── spotify/       # Cleaned views over raw Spotify tables
│   │   │   ├── statsbomb/     # Cleaned views over raw StatsBomb tables
│   │   │   ├── nba/           # Cleaned views over raw NBA box scores
│   │   │   ├── openf1/        # Cleaned views over raw F1 timing data
│   │   │   ├── crypto/        # Cleaned views over raw trade ticks
│   │   │   └── payments/      # Cleaned views over raw payment/rejection events
│   │   └── marts/
│   │       ├── spotify/       # Analysis-ready Spotify tables
│   │       ├── statsbomb/     # Analysis-ready football tables
│   │       ├── nba/           # Analysis-ready NBA game/team/player tables
│   │       ├── crypto/        # Incremental OHLCV candle tables
│   │       └── payments/      # Incremental accept/reject status + per-minute tables
│   ├── macros/                # generate_schema_name override
│   └── profiles.yml           # DuckDB connection + crypto_raw / payments_raw attach
├── dashboards/
│   ├── spotify/               # SvelteKit app — Spotify listening data
│   └── crypto/                # SvelteKit app — real-time trade feed
├── orchestration/             # Dagster package (dagster_data_world)
│   ├── assets/                # Software-defined assets (Spotify, StatsBomb, NBA, dbt)
│   ├── jobs/                  # Job definitions
│   ├── schedules/             # Cron-based schedules
│   ├── sensors/               # crypto_sensor — triggers dbt on new trade data
│   └── resources/             # Spotify API client resource
├── cube/                      # Cube semantic layer (reads marts.* directly)
│   └── model/cubes/           # Cube data model (YAML)
├── data/                      # DuckDB files + live JSON sidecar (gitignored)
│   ├── spotify.duckdb         # Spotify + StatsBomb + NBA + OpenF1 data
│   ├── crypto_raw.duckdb      # Raw crypto trades (consumer-owned)
│   ├── payments_raw.duckdb    # Raw payment requests + rejections (consumer-owned)
│   └── live_data.json         # Atomic JSON sidecar written by the crypto consumer
├── scripts/                   # One-off utility scripts
├── Taskfile.yml               # Task runner
└── requirements.txt           # Python dependencies
```

> Payments is a practice build (see [data-ingestion/payments/README.md](data-ingestion/payments/README.md)) — it follows the same producer/consumer shape as crypto but is not wired into Dagster; run it manually via Task.

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

### Streaming pipeline (Payments)

```
synthetic producer
    │  payments.requests, payments.rejected (0-10 min late)
    ▼
Kafka (localhost:9092)
    │
    ▼
payments/consumer.py
    └──▶ data/payments_raw.duckdb   (raw_payments.raw_requests / raw_rejections)

dbt build (run separately, read-only attach to payments_raw.duckdb)
    └──▶ staging_payments.stg_payments__requests / stg_payments__rejections
    └──▶ marts.payment_status        (pending → accepted/rejected via bounded look-back)
    └──▶ marts.payments_by_minute    (accepted/rejected counts and $ amounts over time)
```

> A practice build for late-arriving events: a payment is `pending` until either
> a rejection lands or a 10-minute grace window elapses. Unlike crypto, payments
> has no Dagster asset, job, or sensor — it's run manually via
> `task payments:producer` / `task payments:consumer` / `task dbt:payments:build`.

### Semantic layer (Cube)

```
data/spotify.duckdb (marts schema)
        │
        ▼
      cube/ (Cube dev server, @cubejs-backend/duckdb-driver)
        │
        ▼
http://localhost:4000
  Playground · SQL API (:15432) · REST/GraphQL API
```

Cube models five marts directly (`cube/model/cubes/`) — no separate ingestion
or dbt step:

| Cube | Mart table |
|---|---|
| `nba_game_results` | `marts.nba_game_results` |
| `nba_player_season_stats` | `marts.nba_player_season_stats` |
| `nba_team_dim` | `marts.nba_team_dim` |
| `spotify_top_artists` | `marts.top_artists_by_period` |
| `spotify_top_tracks` | `marts.top_tracks_by_period` |

It runs standalone via Task, the same way the dashboards do, rather than as a
Dagster asset: there's nothing for it to materialize, it's a long-running
query service. Use `/cube-develop` to scaffold a new cube on top of another mart.

> Cube's DuckDB driver always opens `spotify.duckdb` read-write (no read-only
> option). Don't run `task cube:dev` at the same time as `task dbt:run` or the
> Dagster spotify/nba ingest jobs, which also need write access to the same file.

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

### Payments (synthetic, streaming)

A practice build simulating near-real-time payment accept/reject analytics, with rejections arriving on a second topic up to 10 minutes after the original request. No external API — a synthetic producer generates the events. See [data-ingestion/payments/README.md](data-ingestion/payments/README.md).

| Topic | Schema.Table | Description |
|---|---|---|
| `payments.requests` | `raw_payments.raw_requests` | Every payment request (append-only) |
| `payments.rejected` | `raw_payments.raw_rejections` | Rejections, published 0–10 min after the request |

### OpenF1 (batch)

Formula 1 timing data from the [OpenF1 API](https://openf1.org). No authentication required. Meetings and sessions are full-replaced per season; the per-session tables are incremental — already-loaded sessions are skipped.

| Endpoint | Schema.Table | Description |
|---|---|---|
| `/meetings` | `raw_openf1.raw_openf1_meetings` | Grand Prix weekends for the season |
| `/sessions` | `raw_openf1.raw_openf1_sessions` | Practice / qualifying / race sessions |
| `/drivers` | `raw_openf1.raw_openf1_drivers` | Driver entry list per session |
| `/laps` | `raw_openf1.raw_openf1_laps` | One row per driver per lap (incremental) |
| `/pit` | `raw_openf1.raw_openf1_pit` | Pit stops per session (incremental) |
| `/stints` | `raw_openf1.raw_openf1_stints` | Tyre stints per session (incremental) |
| `/weather` | `raw_openf1.raw_openf1_weather` | Weather time series per session (incremental) |

## dbt models

All models live in `dbt/` and target `data/spotify.duckdb` as the primary database, with `data/crypto_raw.duckdb` and `data/payments_raw.duckdb` each attached read-only (`crypto_raw`, `payments_raw`).

[Elementary](https://docs.elementary-data.com) is integrated as a dbt package. It captures test results, model run history, and row counts into an `elementary` schema on every `dbt build`, and the `edr` CLI generates an HTML observability report from that data.

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
| `stg_nba_games` | `staging_nba` | One row per game; derives `home_team_won` from the winning team id |
| `stg_nba_player_statistics` | `staging_nba` | Traditional player box scores, one row per player per game |
| `stg_nba_team_statistics` | `staging_nba` | Traditional team box scores, one row per team per game |
| `stg_nba_players` | `staging_nba` | Player biographies, one row per player |
| `stg_nba_team_histories` | `staging_nba` | Franchise histories tracking relocations and renames, one row per era |
| `stg_nba_player_statistics_extended` | `staging_nba` | Advanced player box scores (~1996 onward), one row per player per game |
| `stg_nba_team_statistics_extended` | `staging_nba` | Advanced team box scores (~1996 onward), one row per team per game |
| `stg_openf1__meetings` | `staging_openf1` | Grand Prix weekends and testing events, one row per meeting |
| `stg_openf1__sessions` | `staging_openf1` | Practice/qualifying/race/sprint sessions, one row per session |
| `stg_openf1__drivers` | `staging_openf1` | Driver roster per session |
| `stg_openf1__laps` | `staging_openf1` | Per-lap timing data, one row per lap |
| `stg_openf1__pit` | `staging_openf1` | Pit stop events, one row per stop |
| `stg_openf1__stints` | `staging_openf1` | Tyre stints, one row per continuous run on a tyre set |
| `stg_openf1__weather` | `staging_openf1` | Track/weather observations sampled through each session |
| `stg_crypto_trades` | `staging_crypto` | Typed trade ticks with `notional_value` |
| `stg_payments__requests` | `staging_payments` | Payment requests, deduped on `payment_id` (earliest `consumed_at` wins) |
| `stg_payments__rejections` | `staging_payments` | Payment rejections, deduped on `payment_id` |

### Marts (tables)

| Model | Schema | Description |
|---|---|---|
| `top_artists_by_period` | `marts` | One row per artist with rank across all three time ranges |
| `top_tracks_by_period` | `marts` | One row per track with rank across all three time ranges |
| `sb_match_summary` | `marts` | One row per match with aggregate event counts |
| `sb_player_stats` | `marts` | One row per (player, team) with aggregate stats |
| `nba_game_results` | `marts` | One row per game with both teams' box scores pivoted onto a home/away axis |
| `nba_player_career_stats` | `marts` | One row per player, career-level box score totals and shooting splits |
| `nba_player_season_stats` | `marts` | One row per (player, season, game_type) box score totals |
| `nba_player_advanced_career` | `marts` | One row per player, minutes-weighted advanced career efficiency (~1996 on) |
| `nba_team_dim` | `marts` | Conformed franchise dimension, one row per `team_id` with relocation/rename history |
| `nba_team_season_summary` | `marts` | One row per (team, season) win/loss record and scoring averages |
| `nba_team_advanced_profile` | `marts` | One row per (team, season) advanced efficiency metrics (~1996 on) |
| `nba_team_head_to_head` | `marts` | All-time matchup record, one row per ordered (team, opponent) pair |
| `ohlcv_1m` | `marts` | 1-minute OHLCV candles per trading pair (incremental) |
| `ohlcv_1h` | `marts` | 1-hour OHLCV candles per trading pair (incremental) |
| `payment_status` | `marts` | One row per payment with resolved outcome (accepted/rejected/pending); incremental with a 20-min look-back |
| `payments_by_minute` | `marts` | Pre-aggregated accepted/rejected/pending counts and $ amounts per time bucket; incremental |

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
# Start Kafka in KRaft mode (no ZooKeeper)
brew services start kafka

# Create the crypto topic (only needed once)
kafka-topics --create --topic crypto.trades --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Create the two payments topics (only needed once)
kafka-topics --create --topic payments.requests --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
kafka-topics --create --topic payments.rejected --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
```

### Configure

Copy `.env.example` to `.env` in the project root and fill in the values. It covers Spotify OAuth credentials, Kaggle API credentials (required for NBA ingestion), optional OpenF1 range/limit vars, and DuckDB path overrides (`DUCKDB_PATH`, `CRYPTO_DB_PATH`, `PAYMENTS_DB_PATH`, `LIVE_JSON_PATH`).

> Any DuckDB/JSON path variable you set must be an absolute path.

### dbt packages and Elementary

```bash
task dbt:deps              # install dbt packages (elementary + dbt_utils)
task dbt:elementary:init   # create Elementary tracking tables (run once)
```

### Dagster orchestration

```bash
task dagster:install       # install the orchestration package into the venv (run once)
```

### Dashboard dependencies

```bash
task dashboard:install
task dashboard:crypto:install
```

### Cube semantic layer

```bash
task cube:install
```

Copy `cube/.env.example` to `cube/.env` and set `CUBEJS_DB_DUCKDB_DATABASE_PATH`
to the absolute path of `data/spotify.duckdb`.

## Usage

All commands run from the root of `data-world/` using [Task](https://taskfile.dev).

### Ingest

| Command | Description |
|---|---|
| `task ingest` | Clear Spotify cache and run the full Spotify ingest (triggers browser auth on first run) |
| `task ingest:no-cache-clear` | Run Spotify ingest using the existing cached token |
| `task ingest:statsbomb` | Run the StatsBomb ingest (incremental — skips already-loaded matches) |
| `task ingest:nba` | Download the Kaggle NBA dataset (core + extended) and full-replace load into DuckDB |
| `task ingest:openf1` | Run the OpenF1 ingest for 2024 → current season (incremental — skips already-loaded sessions). Set `OPENF1_START_YEAR` / `OPENF1_END_YEAR` to change the range and `OPENF1_SESSION_LIMIT` to cap sessions per run |

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

### Payments streaming

Start both processes in separate terminals:

```bash
task payments:producer   # Synthetic payments → Kafka (requests + delayed rejections)
task payments:consumer   # Kafka → DuckDB
```

| Command | Description |
|---|---|
| `task payments:producer` | Emit synthetic payment requests to `payments.requests`, with ~15% rejected on `payments.rejected` after a 0–10 min delay |
| `task payments:consumer` | Consume both topics, write to `raw_payments.raw_requests` / `raw_rejections` |

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
| `task dbt:crypto:run` / `:test` / `:build` | Run/test/build crypto models only |
| `task dbt:payments:run` / `:test` / `:build` | Run/test/build payments models only |
| `task edr:report` | Generate and open the Elementary observability report |

### Dashboards

| Command | Description |
|---|---|
| `task dashboard:dev` | Start Spotify dashboard at http://localhost:5173 |
| `task dashboard:build` | Build Spotify dashboard for production |
| `task dashboard:crypto:dev` | Start crypto dashboard at http://localhost:5174 |
| `task dashboard:crypto:build` | Build crypto dashboard for production |

### Semantic layer

| Command | Description |
|---|---|
| `task cube:dev` | Start the Cube dev server + Playground at http://localhost:4000 (don't run alongside `task dbt:run` or the Dagster spotify/nba jobs) |

### Full refresh

| Command | Description |
|---|---|
| `task refresh` | Spotify ingest → `dbt:build` |
| `task refresh:statsbomb` | StatsBomb ingest → `dbt:build` |
| `task refresh:nba` | NBA ingest → `dbt:build` |
| `task refresh:openf1` | OpenF1 ingest → `dbt:build` |
| `task refresh:payments` | `dbt:payments:build` only — payments has no one-shot ingest task; run the producer/consumer separately first to land raw data |
| `task refresh:all` | Spotify + StatsBomb + NBA ingest → `dbt:build` |

### Orchestration (Dagster)

Dagster wraps Spotify, StatsBomb, and NBA ingestion, plus all dbt models, as software-defined assets (`spotify_pipeline`, `statsbomb_pipeline`, `nba_pipeline` jobs, each on its own schedule). Crypto has no ingest asset — a `crypto_sensor` instead polls `crypto_raw.duckdb` for new trade data and triggers the `crypto_dbt` job. Payments is not orchestrated at all: no asset, job, sensor, or schedule — it's run manually via the Task commands above, the same way it would be run outside Dagster.

| Command | Description |
|---|---|
| `task dagster:dev` | Start Dagster UI + daemon at http://localhost:3000 |
| `task dagster:install` | Install the orchestration package into the venv (run once) |

## Viewing data directly

- **DBeaver** — connect to `data/spotify.duckdb`, `data/crypto_raw.duckdb`, or `data/payments_raw.duckdb` in Read-Only mode
- **DuckDB CLI** — `duckdb data/spotify.duckdb`, `duckdb data/crypto_raw.duckdb`, or `duckdb data/payments_raw.duckdb`
- **Harlequin** (TUI) — `pip install harlequin && harlequin data/spotify.duckdb`

> Open `crypto_raw.duckdb` / `payments_raw.duckdb` in read-only mode when their consumer is running to avoid lock conflicts.

## Developer tooling

Claude Code skills are registered in `.claude/skills/` for common development tasks:

| Command | Description |
|---|---|
| `/explore-dataset <domain\|table>` | Profile a raw DuckDB dataset before building models; saves an EDA report to `.claude/eda/` |
| `/test-failures [scope]` | Run dbt tests, diagnose failures by querying affected tables, and output a report with suggested fixes |
| `/dbt-develop` | Scaffold a new dbt model (SQL + YAML) following project conventions |
| `/ingest-api-source` | Scaffold a new batch API → DuckDB ingestion pipeline following the Spotify/StatsBomb/NBA pattern |
| `/cube-develop` | Scaffold a new Cube model on top of an existing dbt mart |

## DuckDB version alignment

The Python (`duckdb==1.4.4`) and Node.js (`duckdb@1.4.4`) packages must use the **same version**. A mismatch causes the newer version to attempt a file format migration requiring exclusive write access, which conflicts with other processes. Both are pinned to `1.4.4` — this also matches the `duckdb` version bundled by Cube's `@cubejs-backend/duckdb-driver` (see [Semantic layer (Cube)](#semantic-layer-cube)), which connects to the same `spotify.duckdb` file.
