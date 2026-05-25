# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the project root via [Task](https://taskfile.dev). Check `Taskfile.yml` for the full list — tasks are grouped by concern (dbt, ingestion, streaming, dashboards, orchestration). The Python venv at `.venv/` must exist; tasks activate it automatically.

If invoking dbt directly rather than via Task, run from `dbt/` since `profiles.yml` lives there.

## Architecture

### Pattern

Each data source follows the same shape: an ingestion script writes raw data into a DuckDB schema, dbt transforms it through staging views into mart tables, and an optional SvelteKit dashboard reads the mart layer. Check `data-ingestion/` for ingestion scripts, `dbt/models/` for the transformation layer, and `dashboards/` for frontends.

Two ingestion modes exist:
- **Batch** — a Python script pulls from an API and writes to `data/spotify.duckdb`
- **Streaming** — a producer pushes to a Kafka topic; a consumer reads from Kafka and writes to a dedicated DuckDB file plus a JSON sidecar

### dbt conventions

Models follow a two-layer structure: `staging/` (views, light cleaning) → `marts/` (tables, analysis-ready). Each data source gets its own subdirectory under both layers.

`dbt/macros/generate_schema_name.sql` overrides the default dbt behaviour so `+schema` values in `dbt_project.yml` are used verbatim — schemas land exactly as named, without a `dev_` or target prefix.

Elementary is installed as a dbt package and captures test results and run history into an `elementary` schema on every `dbt build`. Run `task dbt:elementary:init` once after `dbt deps`.

### DuckDB constraints

**Version pinning** — the Python and Node.js `duckdb` packages must be on the same version. A mismatch causes the newer client to attempt a file format migration requiring exclusive write access, which breaks any concurrent process.

**Lock contention** — a streaming consumer holds a write lock on its DuckDB file while running. Any other process (dbt, Dagster, dashboard) must open that file with `read_only=True`. Streaming dashboards should read the JSON sidecar (`data/live_data.json`) rather than querying DuckDB directly to avoid this entirely.

### Dagster orchestration

`orchestration/` is a Python package (`dagster_data_world`) that wraps ingestion and dbt as software-defined assets. It follows the standard Dagster layout: `assets/`, `jobs/`, `schedules/`, `sensors/`, `resources/`. Sensors poll source databases for new data and trigger dbt jobs in response. `DAGSTER_HOME` must point to `orchestration/` — the task handles this.

### SvelteKit dashboards

Each dashboard in `dashboards/` is a SvelteKit SSR app. Data is loaded in `+page.server.ts` — batch dashboards query DuckDB directly (read-only), streaming dashboards read the JSON sidecar via an API route.

## Environment

Required in a `.env` file at the project root — check `.env.example` or `orchestration/dagster_data_world/constants.py` for the expected variable names. DuckDB path variables must be absolute paths.

## Custom skills

`/dbt-develop` — scaffold a new dbt model (SQL + YAML). Reads conventions lazily from `.claude/conventions/` when invoked — check those files for the full dbt and SQL standards.

`/test-failures [scope]` — run dbt tests, diagnose failures by querying the affected tables, and output a markdown report with suggested fixes. Optional scope argument narrows the run (e.g. `marts for spotify`, `staging`, `crypto`).
