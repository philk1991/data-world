# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the project root via [Task](https://taskfile.dev). Check `Taskfile.yml` for the full list — tasks are grouped by concern (lake, dbt, ingestion, streaming, dashboards, orchestration). The Python venv at `.venv/` must exist; tasks activate it automatically.

Postgres must be running (`brew services start postgresql@17`) — it holds the lake's catalog, and nothing that touches batch data works without it. `task lake:status` checks it.

If invoking dbt directly rather than via Task, run from `dbt/` (where `profiles.yml` and `catalogs.yml` live) and export an absolute `LAKE_DATA_PATH` first (e.g. `export LAKE_DATA_PATH=$PWD/../data/lake/` — no `..` left in it). The Taskfile exports it for every task; DuckLake rejects any spelling of the data path other than the absolute one it was created with.

On a fresh clone, run `task lake:init`, `task setup:streaming-dbs`, `task dbt:driver` and `task dbt:deps` before any dbt command. `setup:streaming-dbs` matters because the dbt profile attaches `crypto_raw.duckdb` and `payments_raw.duckdb` read-only on every run, and dbt fails outright if they don't exist yet (normally they're created by the streaming consumers).

For ad-hoc queries against the lake use `task lake:sql SQL="select ..."` (read-only).

## Architecture

### Pattern

Each data source follows the same shape: an ingestion script writes raw data into a `raw_<source>` schema, dbt transforms it through staging views into mart tables, and readers (Cube, nao, SvelteKit dashboards) query the marts. Check `data-ingestion/` for ingestion scripts, `dbt/models/` for the transformation layer, and `dashboards/` for frontends.

Ingestion comes in three shapes:
- **Batch API** — a Python script pulls from an API and writes to the lake (Spotify, StatsBomb open data, OpenF1)
- **Bulk dataset** — a script downloads files from a dataset (NBA, via Kaggle/kagglehub) and full-replaces a set of raw tables in the lake. Loads are idempotent, so re-running picks up the latest upstream snapshot
- **Streaming** — a producer pushes to a Kafka topic; a consumer reads from Kafka and writes to a dedicated DuckDB file (crypto: `data/crypto_raw.duckdb` plus a JSON sidecar; payments: `data/payments_raw.duckdb`, no sidecar). Payments is a practice build simulating late-arriving rejections and is **not** wired into Dagster — run its producer/consumer manually via Task.

### The lake (DuckLake)

All batch and bulk data — raw, staging and marts — lives in one DuckLake named `lake`: Parquet files under `data/lake/` (`LAKE_DATA_PATH`) plus a catalog in the local Postgres database `data_world_lake` (`LAKE_CATALOG`). DuckDB is the engine. Each source is isolated in its own `raw_<source>` schema (`raw_spotify`, `raw_statsbomb`, `raw_nba`, `raw_openf1`); dbt writes `staging_<source>` and `marts`.

`data-ingestion/lake.py` is the one place the Python attach is defined:
- `connect_lake(read_only=False)` — in-memory DuckDB, loads `ducklake` + `postgres`, sets commit-retry settings, attaches the lake as `lake` and runs `USE lake`, so unqualified names like `raw_nba.raw_nba_games` resolve inside the lake.
- `@in_transaction` — decorator for `load_*(conn, ...)` functions: runs the whole load as one commit. **Every loader must use it.** Without it, `executemany` autocommits per row; on the lake each commit is a Postgres transaction plus a snapshot, so this ran at ~11,600 commits/minute, bloated the catalog and starved dbt's commits.
- `maintain_lake(conn, retain="7 days")` — flush inlined data, merge small files, rewrite files with deletes, expire old snapshots, delete unreferenced and orphaned files. Run by `task lake:maintain` and the weekly `lake_maintenance` Dagster job.

The lake locks per commit, not per connection, so ingest jobs, dbt builds and every reader can run at the same time; conflicting commits are retried (`ducklake_max_retry_count` etc., kept in step between `lake.py` and `dbt/profiles.yml`). Readers attach with `READ_ONLY`. Non-Python readers repeat the attach themselves: `cube/cube.js`, `dashboards/spotify/src/lib/server/db.ts`, `nao/nao_config.yaml` — all with the same defaults as `lake.py`.

### Semantic layer (Cube)

`cube/` runs a standalone Cube dev server (`task cube:dev`, Cube 1.8.8) that reads dbt marts directly via `@cubejs-backend/duckdb-driver` — no ingestion or dbt step of its own. It is not a Dagster asset since there's nothing for it to materialize. `cube/cube.js` defines a `driverFactory` whose `initSql` attaches the lake READ_ONLY and runs `USE lake`, so the cube models' `marts.*` names resolve; `CUBEJS_DB_DUCKDB_EXTENSIONS=ducklake,postgres` in `cube/.env` loads the extensions first. The attach uses `IF NOT EXISTS` because `initSql` runs on every connection. Use `/cube-develop` to scaffold a new cube on top of a mart. Dimensions that expose a mart column as-is take the dbt column's description verbatim: `task cube:docs:sync` copies it into the cube YAML (`cube/scripts/sync_dbt_descriptions.py`, reading `dbt/target/manifest.json`) and `task cube:docs:check` fails on drift — so fix descriptions in dbt, never in the cube file. Computed dimensions and measures keep hand-written descriptions. A cube that filters its mart with `sql:` (the NBA cubes keep seasons from 1954-55 by joining `marts.nba_seasons_dim`) names the mart in `meta.dbt_model` so the sync still finds it. The NBA cubes are `public: false`; `cube/model/views/nba.yml` is the published interface (`player_season`, `player_career`, `team_season`, `game`, `player`), with the default scope as view `default_filters` (player views: Regular Season until a query filters `game_type`; `game`: competitive games). The views' descriptions carry the agent guidance, since Cube 1.8.8 has no `ai_context`. Rates in Cube divide sums of component columns the mart exposes (`ts_points`, `efg_three_pointers_made`, …); never re-implement a dbt formula over pre-aggregated totals (`plans/adr/0002-dbt-cube-boundary.md`).

`cube/mcp/server.py` is a local MCP server (Python `mcp` 2.x — `MCPServer`, the renamed FastMCP) that lets Claude answer questions through Cube: `describe_model` (`/meta`), `query` (`/load`, limit capped at 1000) and `generated_sql` (`/sql`). It runs over stdio — `.mcp.json` registers it, so Claude Code starts it from the repo root — and only talks to the Cube dev server on localhost, signing a short-lived JWT with `CUBEJS_API_SECRET` from `cube/.env`. It has its own venv (`task cube:mcp:install`, pins in `cube/mcp/requirements.txt`) and needs `task cube:dev` running; `task cube:mcp:check` smoke-tests it. Claude only sees `public` members (so NBA questions go through the views), and Cube hides primary-key dimensions by default, so mark a key `public: true` if it should be queryable. Answer quality depends on cube descriptions stating grain and weighting.

### Analytics agent (nao)

`nao/` runs [nao](https://github.com/getnao/nao) (`nao-core` 0.3.31, Apache 2.0), a self-hosted agentic analytics agent: `nao sync` builds a file-based context (schema docs under `nao/databases/`, hand-authored context under `nao/docs/`, agent instructions in `nao/RULES.md`) and `task nao:dev` (`nao chat`) serves a chat UI that turns natural-language questions into SQL. It is **complementary to Cube, not competing**: Cube serves defined metrics to BI tools/dashboards, nao answers ad-hoc NL questions over the same marts. Like Cube, it materializes nothing and is **not wired into Dagster** — it only reads.

Currently scoped to the NBA marts via `include: ["lake.marts.nba_*"]` in `nao/nao_config.yaml` (nao's include globs are catalog-qualified for DuckLake). The database is `type: ducklake` with a Postgres catalog; nao attaches it READ_ONLY and then locks down filesystem access to the lake's data path.

Operational caveats specific to nao:

- **Shared venv.** nao is installed in the shared `.venv` from `requirements.txt` as `nao-core[duckdb,ollama]==0.3.31` (the `duckdb` extra brings `pyarrow` — without it `nao sync` silently skips every schema; the `ollama` extra is the client for the local model). The `duckdb==1.5.5` pin in the same file keeps nao on the project's DuckDB. It used to have its own `nao/.venv` because `nao-core` 0.0.x pulled `protobuf` 7, which the Dagster 1.13.26 in `.venv` doesn't accept (it pins protobuf <7). Since 0.3.x nao doesn't depend on protobuf. Its only clash was `python-dotenv` (nao needs >=1.2.1), so that pin moved to 1.2.4.
- **Local LLM.** `llm:` in `nao_config.yaml` points at Ollama's `nao-qwen3:14b`, so chat is free and stays on the machine. That's `qwen3:14b` with a 32K context window, defined in `nao/Modelfile` and built by `task nao:model` (about 9 GB on disk and ~12 GB RAM while loaded). **Don't point nao at a stock Ollama model:** Ollama's default window is 4,096 tokens and it silently drops the start of a longer prompt. nao's prompt is ~11K tokens, so the model loses its instructions and table list and invents table names. `nao chat` needs Ollama running (`brew services start ollama`) and the model built; `nao sync`/`nao debug` don't. nao 0.3.31 also supports openai, anthropic, mistral, gemini, openrouter, requesty, bedrock, vertex, qwen, minimax, moonshot, meta and any OpenAI-compatible endpoint (`openaiCompatible`); hosted ones need a key in `nao/.env`. Every `nao:*` task sets `POSTHOG_DISABLED=true` to turn off nao's usage analytics.
- **Context enrichment.** `task nao:sync` runs `nao sync`, then `nao/scripts/enrich_context.py`. That script (a) writes the marts' dbt descriptions (lake comments, from `persist_docs`) into nao's generated `columns.md` files, because nao 0.3.31's DuckLake context looks comments up under `schema_name = 'lake.marts'` and finds none; and (b) rewrites the `## Columns by table (generated)` section at the end of `nao/RULES.md` with every synced table's exact column names, because the local model guesses names rather than reading `columns.md`; and (c) writes `nao/docs/nba/nba_marts.md` (grain, description, coverage per mart) from dbt's manifest, so don't edit that file either. `task nao:sync` runs `dbt parse` first. Edit RULES.md above the generated heading only; it carries the default scope (seasons from 1954-55, regular-season careers, `is_qualified`). Run `task nao:sync` after a dbt build that changes mart columns or descriptions.
- Accounts and chat history live in `nao/db.sqlite` (gitignored): `task nao:dev` sets `DB_URI` to it. Without that, the chat server writes `db.sqlite` inside `.venv`'s `nao_core` package, and reinstalling nao wipes it. Config in `nao/nao_config.yaml`, secrets in `nao/.env` (see `nao/.env.example`). Validate a setup with `task nao:debug`.

### dbt conventions

dbt runs on **dbt-oss 2.0.8** (dbt v2, Apache-2.0 — not Fusion, and not dbt-core 1.x). Things that differ from dbt 1.x:
- The lake is configured in `dbt/catalogs.yml` (a `ducklake` catalog named `lake`, Postgres `metadata_path`, `data_path` from `LAKE_DATA_PATH`), enabled by the `use_catalogs_v2` flag, and `+catalog_name: lake` in `dbt_project.yml` puts every model in it. `profiles.yml` is an in-memory DuckDB with the `ducklake` and `postgres` extensions, 4 threads, and the read-only streaming attaches.
- dbt-oss reaches DuckDB through an ADBC driver installed by `task dbt:driver` (`dbc install duckdb=1.5.5`). The driver bundled with dbt-oss can't load extensions, so the lake can't attach without it.
- YAML uses the v2 shapes (`config.meta`, generic test `arguments:`) — `dbt-autofix deprecations` produced them.
- `dbt lint` needs the proprietary distribution (`dbt system upgrade-distribution`), so SQL is linted with SQLFluff instead: `task dbt:lint` / `task dbt:fix`, config in `dbt/.sqlfluff`. It uses the `jinja` templater with `apply_dbt_builtins` — the `dbt` templater is built on dbt-core 1.x and can't drive dbt-oss.
- Columns shared by several models of a domain take their description from a doc block in `dbt/models/docs/<domain>.md` (`"{{ doc('nba__season_start_year') }}"`, model-specific context after it); `task dbt:docs:check` (`dbt/scripts/check_column_docs.py`) enforces it. Only NBA has a docs file so far — see `.claude/conventions/dbt-conventions.md`.
- Marts have `+persist_docs` (relation and columns), so model and column descriptions are written into the lake as table/column comments, which nao and DBeaver read. Staging can't: DuckLake rejects column comments on views, and a project-wide setting failed every staging model.
- There's no static analysis, so unit-test fixtures for `TIMESTAMPTZ` columns must be `format: sql` with explicit `::timestamptz` casts (see `models/marts/payments/unit_tests_payments.yml`).

Models follow a two-layer structure: `staging/` (views, light cleaning) → `marts/` (tables, analysis-ready). Each data source gets its own subdirectory under both layers. NBA also has `intermediate/nba/` (tables in `intermediate_nba`): `int_nba_player_games` is every player-game played (all game types, `is_competitive` flag, team recovered where the raw data leaves it blank, double-doubles flagged) and the base of the player game, season and career marts; `int_nba_team_games` pairs each team-game with its opponent and fills pre-1983-84 counts from player sums, the base for every team metric. NBA metric formulas are defined once in `dbt/macros/nba_metrics.sql` (versioned by the `nba_metrics_version` var); scope lives in `dbt/macros/nba_scope.sql` (season label, competitive and career game types, metric coverage years, and the `nba_first_complete_season` var: seasons before 1954-55 are missing games against defunct franchises). Careers are one row per player per scope, Regular Season (default) or Playoffs, additive across the two. Conformed dimensions: `nba_seasons_dim` (coverage tier, current season), `nba_game_types_dim`, `nba_team_seasons_dim` (name as of the season). Decisions and coverage are in `plans/nba-advanced-metrics-decision-log.md`; the dbt/Cube/nao architecture decisions are ADRs in `plans/adr/`, and the project plan is `plans/nba-staff-ae-project.md`. `docs/nba-metrics-field-guide/index.html` is a self-contained explainer of the NBA metric models (lineage, metric dictionary, coverage, last-season samples, column profiles); `task docs:nba-guide` refreshes its embedded samples and profiles from the lake after a build.

`dbt/macros/generate_schema_name.sql` overrides the default dbt behaviour so `+schema` values in `dbt_project.yml` are used verbatim — schemas land exactly as named, without a `dev_` or target prefix.

There is no Elementary (it doesn't run on dbt v2 + DuckDB). Run history is in the Dagster UI; `task dbt:freshness` checks source freshness (the payments feed).

### DuckDB constraints

**Version pinning** — every DuckDB client is on **1.5.5**: Python (`requirements.txt`), the dbt-oss ADBC driver (`task dbt:driver`), Cube (1.8.8 bundles `@duckdb/node-api` 1.5.5-r.5), the Spotify dashboard (`@duckdb/node-api` 1.5.5-r.5) and nao (shares `.venv`). Upgrade them together.

**Lock contention (streaming files only)** — a `.duckdb` file is single-writer. A streaming consumer holds the write lock on its file while running, so any other process (dbt, Dagster's crypto sensor) must open it with `read_only=True`. Streaming dashboards read the JSON sidecar (`data/live_data.json`) rather than querying DuckDB directly. The lake has no such constraint; Dagster ingest assets that write it can run concurrently (the NBA `deps` chain is now just ordering, not lock avoidance).

### Dagster orchestration

`orchestration/` is a Python package (`dagster_data_world`) that wraps ingestion and dbt as software-defined assets. It follows the standard Dagster layout: `assets/`, `jobs/`, `schedules/`, `sensors/`, `resources/`. `DAGSTER_HOME` must point to `orchestration/` — the task handles this. Ingest assets get the lake through `LakeResource` (`resources/lake.py`, wrapping `connect_lake`), and `DbtCliResource` runs the dbt-oss binary.

Each source typically has its own asset job spanning its `<source>_ingest` and `<source>_dbt` asset groups (e.g. `spotify_pipeline`, `statsbomb_pipeline`, `nba_pipeline`), plus a schedule. All dbt models come from one `@dbt_assets` definition; a `DagsterDbtTranslator` assigns each model to a `<source>_dbt` group by file path and maps each dbt source to the ingest asset that writes it, so dbt waits for ingestion. Where ingestion is triggered by data landing rather than a clock (streaming), a sensor polls the source DuckDB file and triggers the dbt job instead — crypto has no ingest asset at all, only a `crypto_dbt` job triggered by `sensors/crypto_sensor.py`. Payments has no Dagster presence whatsoever (no asset, job, sensor, or schedule) — it's a manual-only pipeline; don't assume it follows the same orchestration path as crypto. `lake_maintenance_job` (an op job, not assets) runs `maintain_lake` every Sunday at 05:00.

### SvelteKit dashboards

Each dashboard in `dashboards/` is a SvelteKit SSR app. Data is loaded in `+page.server.ts` — the Spotify dashboard queries the lake through `src/lib/server/db.ts` (`@duckdb/node-api`, READ_ONLY attach, `bigint` → `number`), streaming dashboards read the JSON sidecar via an API route.

## Environment

Required in a `.env` file at the project root — check `.env.example` or `orchestration/dagster_data_world/constants.py` for the expected variable names. Path variables must be absolute paths. Cube and nao have their own `.env` files (`cube/.env`, `nao/.env`).

## Custom skills

Skills live in `.claude/skills/`:

`/dbt-develop` — scaffold a new dbt model (SQL + YAML). Reads conventions lazily from `.claude/conventions/` when invoked — check those files for the full dbt and SQL standards.

`/test-failures [scope]` — run dbt tests, diagnose failures by querying the affected tables, and output a markdown report with suggested fixes. Optional scope argument narrows the run (e.g. `marts for spotify`, `staging`, `crypto`).

`/explore-dataset <domain|table>` — profile a raw dataset (lake or streaming DuckDB file) before building dbt models. Outputs column stats, missing data, top values for categoricals, suggested dbt models, and cross-domain join opportunities. Saves report to `.claude/eda/`.

`/ingest-api-source` — scaffold a new batch API → lake ingestion pipeline following the Spotify/StatsBomb/NBA fetch_/load_ pattern (`connect_lake`, `@in_transaction`). For REST/HTTP sources only — not streaming (Kafka) or bulk dataset downloads.

`/cube-develop` — scaffold a new Cube model (`cube/model/cubes/<mart>.yml`) on top of an existing dbt mart, keeping dimensions/measures aligned with the mart's dbt documentation.
