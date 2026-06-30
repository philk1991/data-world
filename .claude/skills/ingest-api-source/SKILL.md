---
name: ingest-api-source
description: Scaffold a new batch API → DuckDB ingestion pipeline that follows this project's fetch_/load_ pattern. Use this whenever someone wants to add, build, or wire up ingestion for a new REST/HTTP API data source — phrases like "ingest data from <API>", "pull <entities> from this endpoint into DuckDB", "add a new data source", "create an ingestion pipeline", or "load <API> into raw tables". Trigger even when the user names only the API and the objects they want (e.g. "pull posts and users from jsonplaceholder") and doesn't say the word "pipeline".
---

# ingest-api-source

Scaffold a new **batch API ingestion pipeline** that pulls JSON from a REST/HTTP
API and loads it into DuckDB, following the exact pattern the existing Spotify,
StatsBomb, and NBA pipelines use. The point is consistency: every new source
should look like the others so dbt, Dagster, and the dashboards can treat it the
same way.

This skill is for **batch HTTP/REST** sources. It is **not** for streaming
(Kafka producer/consumer — see `crypto/`) or bulk dataset downloads (Kaggle —
see `nba/`). If the user describes a websocket/stream or a "download the whole
dataset" source, say so and stop.

All paths below are relative to the `data-world/` project root. Read
[references/conventions.md](references/conventions.md) and
[references/templates.md](references/templates.md) before writing any code —
they hold the non-negotiable naming rules and the code templates you will fill
in. Don't reinvent the structure from memory; the templates encode decisions
(idempotency, `ingested_at`, typed `CREATE TABLE`, 429 retry) that the rest of
the stack depends on.

## The pattern in one breath

```
data-ingestion/
  ingest_<source>.py              # entry point: load .env, connect DuckDB, call fetch_/load_ per entity
  <source>/
    __init__.py                   # empty
    ingestion/
      __init__.py                 # empty
      <entity>.py                 # fetch_<entity>() -> list[dict]  +  load_<entity>(conn, records)
```

One `fetch_<entity>` / `load_<entity>` pair per entity the user asked for. Each
entity becomes one raw table `raw_<source>.raw_<source>_<entity>`. The entry
point wires them together. A `Taskfile.yml` entry and a README row make it
discoverable.

## Step 1 — Gather intent

You need these before writing anything. If the user gave some in their request,
don't re-ask — only fill gaps.

1. **Source name** — a short lowercase slug (`jsonplaceholder`, `github`,
   `openweather`). Becomes the package dir, the `raw_<source>` schema, the
   `raw_<source>_<entity>` table prefix, the `ingest_<source>.py` entry point,
   and the `ingest:<source>` task. Pick one and use it verbatim everywhere.
2. **Base URL** — e.g. `https://jsonplaceholder.typicode.com`.
3. **Entities** — which endpoints/objects to pull, and the path for each
   (`posts` → `/posts`, `users` → `/users`). One entity = one table.
4. **Auth** — none / API key in header / bearer token / query param. If any,
   the env var name follows `<SOURCE>_API_KEY` (uppercase source). You will add
   it to `.env.example`, never hardcode the secret.
5. **Pagination** — does a list endpoint page (`?page=`, a `next` URL, an
   offset/limit)? Check the probe output in Step 2.
6. **Load strategy per entity** — full-replace or incremental. See
   [references/conventions.md](references/conventions.md#load-strategy). When
   unsure, default to **full-replace**; it's simpler and correct for anything
   that comfortably re-pulls in one run.

## Step 2 — Probe every endpoint (do not skip)

Never infer the schema from the docs or from memory — call the API and look at a
real response. Run the bundled probe for each entity's endpoint:

```bash
source .venv/bin/activate
python .claude/skills/ingest-api-source/scripts/probe_endpoint.py <full-url> [--header "Authorization: Bearer $TOKEN"] [--limit 50]
```

It locates the list of records inside the response (handles a top-level array or
a `{"results": [...]}` / `{"data": [...]}` wrapper), then prints, per field: a
suggested DuckDB column type, a sample value, and a flag for nested
objects/arrays. It also reports whether the response is paginated (a `next`
cursor or `count`/`page` keys).

Use its output to decide:
- **Column list + types** for the typed `CREATE TABLE`. Map JSON → DuckDB per
  [references/conventions.md](references/conventions.md#type-mapping).
- **Nested fields** — flatten the one or two you care about into scalar columns
  (e.g. `address.city` → `address_city`), or drop the rest. Raw tables stay
  flat; deeper structure is dbt's job, not ingestion's.
- **The records key** — what to index into in `fetch_` (top-level list vs
  `payload["results"]`).

## Step 3 — Generate the per-entity modules

For each entity, create `<source>/ingestion/<entity>.py` from the template in
[references/templates.md](references/templates.md). Fill in: the endpoint path,
the records key, the coerced column dict in `fetch_`, and the typed
`CREATE TABLE` + `INSERT` in `load_`. Keep the module docstring — state the
endpoint, the table, and the load strategy, like the existing modules do.

Pick the **full-replace** or **incremental** load template per Step 1.6. If the
list endpoint paginates, use the paginated `fetch_` variant (loop until no
`next` / empty page).

Create the two empty `__init__.py` files (`<source>/__init__.py` and
`<source>/ingestion/__init__.py`) so the package imports.

## Step 4 — Generate the entry point

Create `ingest_<source>.py` at `data-ingestion/` from the entry-point template.
It loads `.env`, resolves `DUCKDB_PATH` (default `../data/spotify.duckdb`),
opens the connection, and calls each `fetch_`/`load_` pair with progress prints,
then closes. Match the docstring shape of `ingest_statsbomb.py` — what it
fetches, the env config, and the `Usage:` line.

## Step 5 — Wire it up

1. **Taskfile** — add an `ingest:<source>` task (copy the shape of
   `ingest:statsbomb`):
   ```yaml
     ingest:<source>:
       desc: Run the <Source> API ingest pipeline
       cmds:
         - bash -c "source {{.VENV}} && cd data-ingestion && python ingest_<source>.py"
   ```
2. **`.env.example`** — if the source needs auth, add the `<SOURCE>_API_KEY`
   line with a comment pointing at where to get it.
3. **READMEs** — add a row to the source table in both `README.md` (root) and
   `data-ingestion/README.md`, matching the existing batch-source rows
   (entry point → destination → task command).

## Step 6 — Run it and verify rows landed

A scaffold that hasn't run is not done. Execute it against a throwaway DuckDB so
you don't touch the real one, then confirm the tables exist with rows and an
`ingested_at`:

```bash
source .venv/bin/activate
DUCKDB_PATH=/tmp/ingest_smoke.duckdb python data-ingestion/ingest_<source>.py
python - <<'PY'
import duckdb
c = duckdb.connect('/tmp/ingest_smoke.duckdb', read_only=True)
for (s, t) in c.execute("select schema_name, table_name from duckdb_tables() where schema_name like 'raw_%' order by 1,2").fetchall():
    n = c.execute(f'select count(*) from "{s}"."{t}"').fetchone()[0]
    print(f"{s}.{t}: {n} rows")
PY
rm -f /tmp/ingest_smoke.duckdb
```

Every requested entity must show a table with `> 0` rows. Re-running the entry
point must not error or duplicate (idempotency — full-replace clears first,
incremental skips loaded keys). If a run fails, read the traceback, fix the
module, re-run — the same loop the README's troubleshooting describes.

## Step 7 — Hand off

Tell the user what you built (files, tables, row counts), how to run it
(`task ingest:<source>`), and the obvious next step: model it with
`/dbt-develop` (a `stg_<source>__<entity>` staging model over each raw table)
and, if it should run on a schedule, add it as a Dagster asset under
`orchestration/`.

## Reference files

- [references/conventions.md](references/conventions.md) — naming rules, the
  JSON→DuckDB type map, `ingested_at`, idempotency, and the full-replace vs
  incremental decision. Read this first.
- [references/templates.md](references/templates.md) — the entity-module and
  entry-point code templates (full-replace, incremental, and paginated
  variants) plus the coercion helpers. Copy and fill these in.
- [scripts/probe_endpoint.py](scripts/probe_endpoint.py) — fetch a sample
  response and suggest a column schema. Run it in Step 2.
