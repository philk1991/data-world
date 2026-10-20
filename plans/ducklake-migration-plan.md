# Migrate the batch platform from `spotify.duckdb` to DuckLake (Postgres catalog)

## Context

Every batch source, dbt, Cube, nao and the Spotify dashboard share one DuckDB file, `data/spotify.duckdb`. DuckDB allows one read-write process per file and it locks out *everyone else* — readers included — for as long as that process stays connected. In practice that has meant:

- A long ingest blocks everything. The OpenF1 backfill held the lock for hours, so dbt, StatsBomb and every reader had to wait.
- Readers and writers can't overlap. Cube's driver always opens the file read-write, so `task cube:dev` can't run alongside `task dbt:run` or a Dagster ingest, and nao/the dashboard can't open the file while either is running.
- Dagster ingest assets have to be chained with `deps` just to avoid contending for the lock.

**DuckLake** (1.0, April 2026) splits the database into Parquet data files on local disk plus a catalog held in a SQL database. With a **Postgres catalog**, locking happens per-commit in Postgres rather than per-connection on a file, so multiple writers and readers can work at once.

This was verified before writing this plan (DuckDB 1.5.2, scratch environment):

| Test | SQLite catalog | Postgres catalog |
|---|---|---|
| Reader + Cube driver while a writer holds a connection open | ✅ | ✅ |
| 2 writers (ingest-style + dbt-style rebuild) | ❌ `database is locked` in 3/4 runs, not fixed by raising `ducklake_max_retry_count` | ✅ 5/5 runs |
| 3 writers × 100 back-to-back commits | ❌ 2 of 3 writers crashed | ✅ 300/300 commits, data verified |
| Cube's real driver (`@cubejs-backend/duckdb-driver` 1.8.8) via `initSql` ATTACH | ✅ queries + schema introspection | ✅ |

Cost: **zero**. Postgres 17 runs locally via Homebrew (already installed, `brew services start postgresql@17`); data stays on local disk. No cloud storage or paid services.

## Target architecture

```
                 ┌───────────────────────────── writers (concurrent) ─────────────────────────────┐
  ingest scripts ─┤ Spotify · StatsBomb · NBA · OpenF1     dbt-oss build (staging → marts)         ├─┐
  (+ Dagster)     └────────────────────────────────────────────────────────────────────────────────┘ │
                                                                                                     ▼
                  DuckLake "lake"  =  Postgres catalog (db: data_world_lake)  +  Parquet in data/lake/
                                                                                                     ▲
                 ┌──────────────────────────── readers (concurrent, READ_ONLY) ────────────────────┐ │
                 │  Cube · nao · Spotify dashboard · ad-hoc DuckDB / Claude Code                     ├─┘
                 └──────────────────────────────────────────────────────────────────────────────────┘

  Streaming (unchanged in this migration): crypto_raw.duckdb / payments_raw.duckdb, attached read-only by dbt
```

## Key decisions

1. **Postgres catalog, not SQLite.** SQLite fails with concurrent writers (see table above), which is the main problem we're solving.
2. **Keep every schema name as it is** (`raw_*`, `staging_*`, `marts`) inside one lake called `lake`. Every connection runs `USE lake` after attaching, so dbt model SQL, ingest `load_*` functions and Cube `sql_table: marts.*` references don't change.
3. **One shared connection helper** (`data-ingestion/lake.py`: `connect_lake(read_only=False)`), used by ingest scripts, Dagster and one-off scripts, so the ATTACH string is defined in one place. It's driven by two env vars:
   - `LAKE_CATALOG=postgres:dbname=data_world_lake host=localhost` (Homebrew Postgres uses local trust auth, so there's no password)
   - `LAKE_DATA_PATH=/abs/path/to/data-world/data/lake/` (absolute, per the repo's path convention)
4. **Pin DuckDB to 1.5.5 everywhere** — Python `duckdb==1.5.5`, `@duckdb/node-api@1.5.5-r.5` (what Cube 1.8.8 bundles), and the `dbc`-installed DuckDB driver that dbt-oss uses (`dbc install "duckdb=1.5.5"`). This keeps the existing "Python and Node DuckDB versions must match" rule. (DuckLake 1.0 needs ≥ 1.5.2.)
5. **Streaming stays out of scope for now.** The crypto and payments consumers keep their own DuckDB files, and the JSON sidecar and `setup:streaming-dbs` stay. Moving them into the lake is an optional Phase 7. Frequent tiny appends create many small Parquet files, so it's worth tackling separately once the maintenance job has proven itself.
6. **Do the work on a branch** (`ducklake-migration`). Leave `spotify.duckdb` untouched until sign-off, because it's the rollback.
7. **Upgrade to dbt v2 using `dbt-oss`** (2.0.8, the Apache-2.0 distribution, which matches what work runs), not the proprietary Fusion `dbt` package. **Remove Elementary**: it fails on dbt v2 + DuckDB. The payments sources' Elementary freshness checks become built-in source `freshness`, and the volume-anomaly checks are dropped. dbt v2 builds safely on 4 threads, so the dbt 1.x `threads: 1` workaround isn't needed.

## Phases

Each phase ends with a verification gate. Don't start the next phase until it passes.

### Phase 0 — Close the remaining unknowns (spike, scratch only)

The core concurrency question is answered. These smaller compatibility questions are still open, and each one gets a scratch test:

- **dbt-duckdb on DuckLake:** exact `profiles.yml` shape (`attach` with `is_ducklake: true` + target `database: lake`). Do **views** (all staging models), **tables**, and the **incremental** `unique_key` model (`marts/crypto/ohlcv_1h.sql`) all build? dbt-duckdb 1.10.1 → 1.11.0 if needed.
- **Elementary on DuckLake:** does `dbt run --select elementary` and the on-run-end hook work, and does `edr report` read it?
- **Cube `initSql`:** does the driver accept multiple statements (`ATTACH …; USE lake;`) in one `initSql`, or do we need `CUBEJS_DB_DUCKDB_SCHEMA`/fully qualified names instead?
- **nao 0.3.25** `type: ducklake` with `catalog.type: postgres`: does an empty password pass its validator? Does `nao sync` work?
- **Maintenance:** confirm DuckLake 1.0's compaction/cleanup calls (`ducklake_merge_adjacent_files`, `ducklake_expire_snapshots`, `ducklake_cleanup_old_files`, or `CHECKPOINT`) and what each one does.

**dbt v2 track.** We want to move to dbt v2 (GA 14 Sept 2026, Fusion engine, free for local use) eventually. On v2, DuckLake is configured through `catalogs.yml` (`type: ducklake`, `metadata_path`/`data_path`, `use_catalogs_v2` flag, models pick it up via `catalog_name`) rather than through a `profiles.yml` attach. Settling this now avoids doing Phase 3 twice. In a scratch copy of `dbt/`:

- Install dbt v2 (`pip install dbt` → binary) **plus a DuckDB driver via `dbc`**. v2's bundled driver can't load extensions, and DuckLake and the Postgres catalog connection are both extensions. Record which DuckDB version the dbc driver gives us, because it has to line up with the 1.5.5 pin in decision 4.
- Can `catalogs.yml` point `metadata_path` at the Postgres catalog (`postgres:dbname=data_world_lake host=localhost`, or via a named secret)? Is `catalog_name` settable once at folder level in `dbt_project.yml` (`+catalog_name`) rather than per model?
- Run `dbt-autofix`, then `dbt parse`. Record anything v2's stricter parse rejects (unknown config keys, deprecations, YAML anchors, the `generate_schema_name` override).
- Build the same three model types as the v1 check: views, tables and the `ohlcv_1h` incremental model.
- **Elementary:** does the package (allows `<3.0.0`) build, does its on-run-end hook run, and does the separate `edr report` CLI read the results when dbt is the v2 binary?
- **Dagster:** does `dagster-dbt` load the v2 manifest and run `dbt build` through the v2 binary (its Fusion support drops the `dbt-core` dependency)?

**Gate:** each question answered. Any blocker gets a written workaround, or we stop and rethink before touching the repo. Then **decide the dbt target for Phase 3:**

- **All v2 items pass → Phase 3 targets dbt v2 directly** (`catalogs.yml`). The upgrade lands as part of the migration, and Phase 3 only happens once.
- **Any v2 item fails → Phase 3 stays on dbt 1.x** (`profiles.yml` attach, already proven). The dbt v2 upgrade becomes a separate follow-up project, and the failing item is written down as what has to change first.

#### Phase 0 results (20 Oct 2026) — **passed; Phase 3 targets dbt-oss v2 with Elementary removed** (decision revised after the dbt 1.x results below; see the dbt-oss row)

Tested in scratch against a Postgres-catalog lake holding a full copy of the real raw data (17 tables, row counts verified), with the DuckDB file copy as the baseline. The baseline is 339 pass / 5 warn / 7 errors, and all the errors are StatsBomb having no data.

| Item | Result |
|---|---|
| dbt 1.x (dbt-core 1.12.6, dbt-duckdb 1.11.0, DuckDB 1.5.5) | ✅ **with `threads: 1`** — identical to baseline on two consecutive builds (views, tables, the incremental `ohlcv_1h`). With 4 threads it **breaks**: dbt's view/table replace (create `__dbt_tmp` → rename → drop backup) running concurrently in one process corrupted the DuckLake catalog (`could not find schema that corresponds to the view entry`). Reproduced outside dbt (catalog broken 2/3 runs for views; tables error 3/4 threads). `CREATE OR REPLACE` is safe concurrently. dbt-duckdb only has DuckLake workarounds for tables below DuckDB 1.5.3, none for views. **Workaround: `threads: 1` on the lake target** (build ~37s vs ~16s). A possible later improvement is overriding the view/table materializations to use `CREATE OR REPLACE`, then putting threads back up. Worth reporting upstream. |
| dbt + a concurrent ingest process | ✅ two 1-thread builds while a separate writer committed 484 OpenF1-style delete+insert reloads — 0 failures, data intact |
| Elementary (dbt package + `edr report`) | ✅ on 1.x — artifact models built; test results match the dbt run (3 fail / 5 warn / 272 pass); report generated |
| Profile shape | `path: ":memory:"`, `database: lake`, `extensions: [ducklake, postgres]`, `attach: - {path: "ducklake:postgres:dbname=… host=localhost", alias: lake, is_ducklake: true, options: {data_path: …}}`, plus the existing streaming attaches |
| Cube driver 1.8.8 | ✅ multi-statement `initSql` (`ATTACH … READ_ONLY; USE lake;`) works; unqualified `marts.*` resolves; `tablesSchema()` sees the marts; writes refused |
| nao 0.3.25 | ✅ `type: ducklake` + `catalog: {type: postgres, …, password: ""}` connects; `nao sync` wrote all 8 NBA marts. Two config changes are needed: **`include` must be lake-qualified (`lake.marts.nba_*`)**, and `accessors` is renamed `templates` (the `description` template is gone). nao's venv resolved DuckDB **1.5.6**, so pin `duckdb==1.5.5` there too. `nao test` now exists. |
| Maintenance | ✅ `ducklake_merge_adjacent_files`, `ducklake_rewrite_data_files`, `ducklake_flush_inlined_data`, `ducklake_expire_snapshots(older_than => …)`, `ducklake_cleanup_old_files(cleanup_all => true)` — expiring 1,036 snapshots + cleanup took the lake 146→134 MB, data intact |
| DuckDB 1.5.5 ↔ 1.4.4 file compatibility | ✅ a file written by 1.5.5 (storage `v1.0.0+`) is still readable by Python and Node 1.4.4, so `.venv` can be upgraded in Phase 1 before the readers move in Phase 5 |
| **dbt v2** (2.0.9 + `dbc` DuckDB driver 1.5.5) | ❌ **for now.** `dbt-autofix` changes are mechanical (meta → `config.meta`, test `arguments`, drop `target-path`); parse passes; `catalogs.yml` with a Postgres `metadata_path` + folder-level `+catalog_name` works; the lake becomes the session default; **4-thread builds don't corrupt the catalog**. **Blocker: Elementary's artifact models fail on dbt v2 + DuckDB** (0.23.1 and 0.26.1), and they fail **on a plain DuckDB file too**, so it's not DuckLake-specific. Superseded: we're dropping Elementary and using dbt-oss (next rows). |
| **dbt-oss 2.0.8** (Apache-2.0) + `dbc` DuckDB 1.5.5, Elementary removed | ✅ deps/parse; `catalogs.yml` DuckLake with a Postgres `metadata_path` works; it uses the `dbc` driver (DuckDB 1.5.5, `ducklake` + `postgres` loaded). **Full build on 4 threads, 3 runs: 303 pass / 5 warn / 7 err (all StatsBomb) / 81 skip — exactly the dbt 1.x baseline minus the 36 Elementary nodes (339 → 303), with no catalog corruption.** 4-thread builds with a concurrent ingest (139 commits): 0 failures. Incremental, `source freshness` and `docs generate` work. **One difference from Fusion:** unit tests reject `TIMESTAMPTZ` fixture columns (dbt-oss has no static analysis, so it takes types from the driver, which reports TIMESTAMPTZ as a struct). Fix: `format: sql` fixtures with explicit `::timestamptz` casts — the `payment_status` unit test then passes, and the model is unchanged. |
| **Dagster with the dbt-oss binary** | ✅ `dagster-dbt` 0.29.26 installs **without** dbt-core, so dbt-oss provides the only `dbt` command. dbt-oss writes a standard v12 manifest (395 nodes). Definitions validate unchanged; the asset graph matches today's (same `<source>_dbt` groups, sources mapped to their ingest assets, 0 Elementary nodes). Through `DbtCliResource`: `crypto_dbt` job → RUN_SUCCESS (3 assets incl. incremental `ohlcv_1h`); `group:nba_dbt` → RUN_SUCCESS, 15 materializations + 100 asset checks. The `select="package:spotify"` filter in `dbt_assets.py` can stay (harmless) or be simplified once Elementary is gone. |

### Phase 1 — Foundation

- `requirements.txt`: `duckdb==1.5.5`, dbt-duckdb 1.11.0 (interim — Phase 3 replaces dbt-core/dbt-duckdb with dbt-oss).
- `data-ingestion/lake.py`: `connect_lake(read_only=False)` → `duckdb.connect()` → `INSTALL/LOAD ducklake, postgres` → `ATTACH 'ducklake:{LAKE_CATALOG}' AS lake (DATA_PATH '{LAKE_DATA_PATH}'[, READ_ONLY])` → `USE lake`.
- Taskfile `lake:init`: idempotent — `createdb data_world_lake` if missing, `mkdir -p data/lake`, attach once to initialise the lake. Add a `lake:status` task that runs `pg_isready`, lists the lake's schemas and shows snapshot count.
- `.env.example`: `LAKE_CATALOG`, `LAKE_DATA_PATH`. Add `data/lake/` to `.gitignore` (it's already covered by `/data/`, but make it explicit).

**Gate:** `task lake:init` works from scratch and on a re-run, and `python -c "from lake import connect_lake; connect_lake()"` attaches.

### Phase 2 — Copy existing data into the lake

- `scripts/migrate_to_lake.py`: attach `spotify.duckdb` **read-only** plus the lake, then `CREATE TABLE lake.<schema>.<t> AS SELECT * FROM old.<schema>.<t>` for every `raw_*` table. This avoids re-ingesting, which saves hours of OpenF1 API calls. Staging, marts and Elementary get rebuilt by dbt in Phase 3, not copied.
- Compare row counts between the old file and the lake for every raw table, and fail loudly on any mismatch.

**Gate:** row counts match for every `raw_*` table, and `spotify.duckdb` is unchanged (it's opened read-only).

### Phase 3 — Point dbt at the lake

Target: **dbt-oss 2.0.8 with Elementary removed** (decision 7). Each item was proven in Phase 0:

- **Install:** in `requirements.txt`, replace `dbt-core`/`dbt-duckdb`/`elementary-data` with `dbt-oss==2.0.8` and `dbc` (both install a `dbt` command, so they can't coexist). Add a `task dbt:driver` (`dbc install "duckdb=1.5.5"`) and add it to the README setup steps.
- **`dbt-autofix deprecations`:** commit its mechanical changes (`meta` → `config.meta`, test `arguments`, drop `target-path`, `require_generic_test_arguments_property` flag).
- **Lake:** add `dbt/catalogs.yml` (`type: ducklake`, `metadata_path: postgres:dbname=data_world_lake host=localhost`, `data_path` from `LAKE_DATA_PATH`), the `use_catalogs_v2` flag and a folder-level `+catalog_name: lake` in `dbt_project.yml`. `profiles.yml` becomes `path: ":memory:"`, `extensions: [ducklake, postgres]`, `threads: 4`, and keeps the read-only `crypto_raw`/`payments_raw` attaches.
- **Remove Elementary:** `packages.yml`, the `elementary` profile, both `elementary` blocks in `dbt_project.yml`, the `dbt:elementary:init`/`edr:report` tasks, and `package-lock.yml` (regenerated by `dbt deps`). The payments sources' anomaly tests become `config: {loaded_at_field: consumed_at, freshness: {warn_after: {count: 1, period: hour}}}`.
- **Unit test:** convert the `payment_status` fixtures to `format: sql` with `::timestamptz` casts.
- **Check Taskfile dbt tasks against dbt-oss:** e.g. `dbt docs serve` → `dbt docs generate` + its v2 equivalent; `--profiles-dir` usage.

Then `task dbt:deps` → `task dbt:build` (full project).

**Gate:** `dbt build` matches the dbt 1.x baseline minus the Elementary nodes (Phase 0: 303 pass / 5 warn / 7 err (StatsBomb, no data) / 81 skip with sample streaming data). Mart row counts match the old file, and `dbt source freshness` runs.

### Phase 4 — Point the writers at the lake

- The four batch scripts (`ingest.py`, `ingest_statsbomb.py`, `ingest_nba.py`, `ingest_openf1.py`): replace `duckdb.connect(db_path)` with `connect_lake()`. The `load_*`/`fetch_*` modules don't change, thanks to `USE lake`.
- Dagster: add a small `LakeResource` (`ConfigurableResource` wrapping `connect_lake`) to replace `DuckDBResource(database=DUCKDB_PATH)` in `__init__.py` and the `spotify`/`statsbomb`/`nba` assets. Update `constants.py`. `DbtCliResource` runs the dbt-oss binary (per the Phase 0 Dagster check). Keep the NBA `deps` chain for now (it's harmless) and revisit once concurrency is proven.

**Gate:** each `task ingest:*` runs. Most importantly, **run the concurrency check for real:** `task ingest:openf1` and `task dbt:build` at the same time, while `task cube:dev` and the dashboard are running. All must succeed.

### Phase 5 — Point the readers at the lake

- **Cube:** upgrade `@cubejs-backend/*` 1.6.65 → 1.8.x. `cube/cube.js` gets a `driverFactory` returning `DuckDBDriver({ databasePath: ':memory:', initSql: <attach READ_ONLY + USE lake> })`. `cube/.env` adds `CUBEJS_DB_DUCKDB_EXTENSIONS=ducklake,postgres` and drops the database path. Cube model YAML doesn't change.
- **Spotify dashboard:** move from `duckdb` (legacy package, last release 1.4.4) to `@duckdb/node-api@1.5.5-r.5`. Rewrite `src/lib/server/db.ts` (an in-memory instance + read-only ATTACH + `USE lake`), and keep the `query()` signature so `+page.server.ts` doesn't change. Fix any differences in returned value types (BigInt/DECIMAL handling) in one place.
- **Crypto dashboard:** remove its unused `duckdb` dependency (it only reads `live_data.json`).
- **nao:** upgrade to `nao-core` 0.3.25 in its isolated venv. In `nao_config.yaml`, switch to `type: ducklake`, `catalog: {type: postgres, host: localhost, database: data_world_lake, user: <you>, password: ""}`, with `data_path` from env and the `marts.nba_*` scope kept. Check `nao debug` and `nao sync`. (This is the deferred nao upgrade. Adding an LLM provider stays a separate decision.)

**Gate:** Cube Playground returns the existing `nba_*` and Spotify cubes; the dashboard renders; `nao sync` regenerates `nao/databases/**` — all **while a dbt build is running**.

### Phase 6 — Operations and docs

- **Maintenance:** a `task lake:maintain` task that runs the Phase 0 compaction/snapshot-expiry/cleanup calls, plus a weekly Dagster schedule for it.
- **CLAUDE.md:** remove the Elementary paragraph and update the dbt section for dbt-oss (`catalogs.yml`, `dbc` driver); rewrite the "DuckDB constraints" and "Lock contention" sections (the single-writer rule now only applies to the streaming files), update the Cube and nao sections, and add a short "Lake" section (catalog, data path, `USE lake`, Postgres must be running). Also update the README setup steps (`brew services start postgresql@17`, `task lake:init`, `task dbt:driver`) and remove its Elementary sections, and the root and `cube/` `.env.example` files.
- **Retire the old file:** after a week of normal use, delete `spotify.duckdb`, `DUCKDB_PATH`, and `scripts/migrate_schemas.py`, which only ever migrated the old file.

**Gate:** a fresh clone can follow the README to a working setup. Do this as an end-to-end check in a scratch clone.

### Phase 7 — Optional, later: move streaming into the lake

The consumers write to the lake. The crypto sensor polls the lake's snapshots instead of a file. The JSON sidecar and `setup:streaming-dbs` could go. Only do this after Phase 6's maintenance job has proven it copes with many small files.

## Rollback

Everything happens on the `ducklake-migration` branch, and `spotify.duckdb` is only ever opened read-only (in Phase 2). To roll back, check out `main`. Dropping the Postgres database (`dropdb data_world_lake`) and `data/lake/` removes everything the migration created.

## Risks

- **Postgres becomes a required service.** If it isn't running, every component fails. Mitigations: a clear error in `connect_lake()` ("is Postgres running? `brew services start postgresql@17`") and `pg_isready` in `lake:status`.
- **Upgrading the DuckDB 1.4 → 1.5 libraries** could change behaviour. The Phase 3 gate (same dbt results, same row counts) is the check.
- **Upgrading Cube 1.6 → 1.8** may change config defaults or Playground behaviour. It's isolated to `cube/`, so it can be rolled back on its own.
- **dbt v2 is new (GA Sept 2026), and dbt-oss lacks Fusion's static analysis.** Proven end to end in Phase 0, but expect rough edges like the `TIMESTAMPTZ` unit-test fixtures. It also needs a separately installed (`dbc`) DuckDB driver, a fourth DuckDB copy to keep in step with Python, Node and Cube.
- **Losing Elementary** means no stored test-result history, anomaly detection or HTML report. Run history remains in the Dagster UI, and source freshness covers the payments feed.
- **Small-file growth** from OpenF1's per-session writes. The Phase 6 maintenance job handles it, and data inlining absorbs tiny writes in the meantime.

## Not in scope

Moving streaming into the lake (Phase 7), adding an LLM provider to nao, cloud or object storage, and Verano (already removed). The dbt v2 upgrade (dbt-oss) and Elementary removal are in scope as part of Phase 3.
