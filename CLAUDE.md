# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the project root via [Task](https://taskfile.dev). Check `Taskfile.yml` for the full list — tasks are grouped by concern (dbt, ingestion, streaming, dashboards, orchestration). The Python venv at `.venv/` must exist; tasks activate it automatically.

If invoking dbt directly rather than via Task, run from `dbt/` since `profiles.yml` lives there.

## Architecture

### Pattern

Each data source follows the same shape: an ingestion script writes raw data into a DuckDB schema, dbt transforms it through staging views into mart tables, and an optional SvelteKit dashboard reads the mart layer. Check `data-ingestion/` for ingestion scripts, `dbt/models/` for the transformation layer, and `dashboards/` for frontends.

Ingestion comes in three shapes:
- **Batch API** — a Python script pulls from an API and writes to `data/spotify.duckdb` (Spotify, StatsBomb open data)
- **Bulk dataset** — a script downloads files from a dataset (NBA, via Kaggle/kagglehub) and full-replaces a set of raw tables. Loads are idempotent, so re-running picks up the latest upstream snapshot
- **Streaming** — a producer pushes to a Kafka topic; a consumer reads from Kafka and writes to a dedicated DuckDB file plus a JSON sidecar

All batch and bulk sources share a single DuckDB file (`data/spotify.duckdb`), each isolated in its own `raw_<source>` schema (`raw_spotify`, `raw_statsbomb`, `raw_nba`, …). Only streaming sources get a dedicated DuckDB file, because the consumer holds a write lock while running.

### dbt conventions

Models follow a two-layer structure: `staging/` (views, light cleaning) → `marts/` (tables, analysis-ready). Each data source gets its own subdirectory under both layers.

`dbt/macros/generate_schema_name.sql` overrides the default dbt behaviour so `+schema` values in `dbt_project.yml` are used verbatim — schemas land exactly as named, without a `dev_` or target prefix.

Elementary is installed as a dbt package and captures test results and run history into an `elementary` schema on every `dbt build`. Run `task dbt:elementary:init` once after `dbt deps`.

### DuckDB constraints

**Version pinning** — the Python and Node.js `duckdb` packages must be on the same version. A mismatch causes the newer client to attempt a file format migration requiring exclusive write access, which breaks any concurrent process.

**Lock contention** — a streaming consumer holds a write lock on its DuckDB file while running. Any other process (dbt, Dagster, dashboard) must open that file with `read_only=True`. Streaming dashboards should read the JSON sidecar (`data/live_data.json`) rather than querying DuckDB directly to avoid this entirely.

The shared `spotify.duckdb` file is also single-writer: ingest assets that write it must not run concurrently. Within a Dagster job, chain such assets with `deps` so they execute serially (e.g. the NBA ingest assets form a chain) rather than letting the executor run them in parallel and contend for the write lock.

### Dagster orchestration

`orchestration/` is a Python package (`dagster_data_world`) that wraps ingestion and dbt as software-defined assets. It follows the standard Dagster layout: `assets/`, `jobs/`, `schedules/`, `sensors/`, `resources/`. `DAGSTER_HOME` must point to `orchestration/` — the task handles this.

Each source typically has its own asset job spanning its `<source>_ingest` and `<source>_dbt` asset groups (e.g. `spotify_pipeline`, `statsbomb_pipeline`, `nba_pipeline`), plus a schedule. All dbt models come from one `@dbt_assets` definition; a `DagsterDbtTranslator` assigns each model to a `<source>_dbt` group by file path and maps each dbt source to the ingest asset that writes it, so dbt waits for ingestion. Where ingestion is triggered by data landing rather than a clock (streaming), a sensor polls the source DuckDB file and triggers the dbt job instead (see `sensors/crypto_sensor.py`).

### SvelteKit dashboards

Each dashboard in `dashboards/` is a SvelteKit SSR app. Data is loaded in `+page.server.ts` — batch dashboards query DuckDB directly (read-only), streaming dashboards read the JSON sidecar via an API route.

## Environment

Required in a `.env` file at the project root — check `.env.example` or `orchestration/dagster_data_world/constants.py` for the expected variable names. DuckDB path variables must be absolute paths.

## Custom skills

`/dbt-develop` — scaffold a new dbt model (SQL + YAML). Reads conventions lazily from `.claude/conventions/` when invoked — check those files for the full dbt and SQL standards.

`/test-failures [scope]` — run dbt tests, diagnose failures by querying the affected tables, and output a markdown report with suggested fixes. Optional scope argument narrows the run (e.g. `marts for spotify`, `staging`, `crypto`).

`/explore-dataset <domain|table>` — profile a raw DuckDB dataset before building dbt models. Outputs column stats, missing data, top values for categoricals, suggested dbt models, and cross-domain join opportunities. Saves report to `.claude/eda/`.
