# Migrate the batch platform from `spotify.duckdb` to DuckLake (Postgres catalog)

## Context

Every batch source, dbt, Cube, nao and the Spotify dashboard share one DuckDB file, `data/spotify.duckdb`. DuckDB allows one read-write process per file and it locks out *everyone else* — readers included — for as long as that process stays connected. In practice that has meant:

- A long ingest blocks everything. The OpenF1 backfill held the lock for hours, so dbt, StatsBomb, Elementary and every reader had to wait.
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
  ingest scripts ─┤ Spotify · StatsBomb · NBA · OpenF1     dbt build (staging → marts, Elementary) ├─┐
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
2. **Keep every schema name as it is** (`raw_*`, `staging_*`, `marts`, `elementary`) inside one lake called `lake`. Every connection runs `USE lake` after attaching, so dbt model SQL, ingest `load_*` functions and Cube `sql_table: marts.*` references don't change.
3. **One shared connection helper** (`data-ingestion/lake.py`: `connect_lake(read_only=False)`), used by ingest scripts, Dagster and one-off scripts, so the ATTACH string is defined in one place. It's driven by two env vars:
   - `LAKE_CATALOG=postgres:dbname=data_world_lake host=localhost` (Homebrew Postgres uses local trust auth, so there's no password)
   - `LAKE_DATA_PATH=/abs/path/to/data-world/data/lake/` (absolute, per the repo's path convention)
4. **Pin DuckDB to 1.5.5 everywhere** — Python `duckdb==1.5.5`, and `@duckdb/node-api@1.5.5-r.5`, which is what Cube 1.8.8 bundles. This keeps the existing "Python and Node DuckDB versions must match" rule. (DuckLake 1.0 needs ≥ 1.5.2.)
5. **Streaming stays out of scope for now.** The crypto and payments consumers keep their own DuckDB files, and the JSON sidecar and `setup:streaming-dbs` stay. Moving them into the lake is an optional Phase 7. Frequent tiny appends create many small Parquet files, so it's worth tackling separately once the maintenance job has proven itself.
6. **Do the work on a branch** (`ducklake-migration`). Leave `spotify.duckdb` untouched until sign-off, because it's the rollback.

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

#### Phase 0 results (20 Oct 2026) — **passed; Phase 3 targets dbt 1.x**

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
| **dbt v2** (2.0.9 + `dbc` DuckDB driver 1.5.5) | ❌ **for now.** `dbt-autofix` changes are mechanical (meta → `config.meta`, test `arguments`, drop `target-path`); parse passes; `catalogs.yml` with a Postgres `metadata_path` + folder-level `+catalog_name` works; the lake becomes the session default; **4-thread builds don't corrupt the catalog**. **Blocker: Elementary's artifact models fail on dbt v2 + DuckDB** (0.23.1 and 0.26.1), and they fail **on a plain DuckDB file too**, so it's not DuckLake-specific. The dbt v2 upgrade becomes a follow-up, gated on Elementary support (or dropping Elementary). |

### Phase 1 — Foundation

- `requirements.txt`: `duckdb==1.5.5`, dbt-duckdb version from Phase 0.
- `data-ingestion/lake.py`: `connect_lake(read_only=False)` → `duckdb.connect()` → `INSTALL/LOAD ducklake, postgres` → `ATTACH 'ducklake:{LAKE_CATALOG}' AS lake (DATA_PATH '{LAKE_DATA_PATH}'[, READ_ONLY])` → `USE lake`.
- Taskfile `lake:init`: idempotent — `createdb data_world_lake` if missing, `mkdir -p data/lake`, attach once to initialise the lake. Add a `lake:status` task that runs `pg_isready`, lists the lake's schemas and shows snapshot count.
- `.env.example`: `LAKE_CATALOG`, `LAKE_DATA_PATH`. Add `data/lake/` to `.gitignore` (it's already covered by `/data/`, but make it explicit).

**Gate:** `task lake:init` works from scratch and on a re-run, and `python -c "from lake import connect_lake; connect_lake()"` attaches.

### Phase 2 — Copy existing data into the lake

- `scripts/migrate_to_lake.py`: attach `spotify.duckdb` **read-only** plus the lake, then `CREATE TABLE lake.<schema>.<t> AS SELECT * FROM old.<schema>.<t>` for every `raw_*` table. This avoids re-ingesting, which saves hours of OpenF1 API calls. Staging, marts and Elementary get rebuilt by dbt in Phase 3, not copied.
- Compare row counts between the old file and the lake for every raw table, and fail loudly on any mismatch.

**Gate:** row counts match for every `raw_*` table, and `spotify.duckdb` is unchanged (it's opened read-only).

### Phase 3 — Point dbt at the lake

Follow whichever dbt target Phase 0 chose:

- **dbt 1.x:** `dbt/profiles.yml` (`spotify` + `elementary` profiles) attaches the lake (`ducklake:` + `is_ducklake: true`), and keeps the read-only `crypto_raw`/`payments_raw` attaches.
- **dbt v2:** apply the `dbt-autofix` changes from Phase 0. Add `dbt/catalogs.yml` with the Postgres-catalog lake, `use_catalogs_v2` and folder-level `+catalog_name` in `dbt_project.yml`. Swap `dbt-core`/`dbt-duckdb` in `requirements.txt` for the v2 install, and document the `dbc` driver install in the README and Taskfile. The streaming attaches move to whatever v2 supports for read-only secondary databases.

Then, either way: `task dbt:build` (full project) → `task dbt:elementary:init`.

**Gate:** `dbt build` gives the same pass/warn/fail counts as on `spotify.duckdb` (today: Spotify 64 pass; NBA 112 pass + 5 expected warns; OpenF1 3 known stint failures). Mart row counts match the old file.

### Phase 4 — Point the writers at the lake

- The four batch scripts (`ingest.py`, `ingest_statsbomb.py`, `ingest_nba.py`, `ingest_openf1.py`): replace `duckdb.connect(db_path)` with `connect_lake()`. The `load_*`/`fetch_*` modules don't change, thanks to `USE lake`.
- Dagster: add a small `LakeResource` (`ConfigurableResource` wrapping `connect_lake`) to replace `DuckDBResource(database=DUCKDB_PATH)` in `__init__.py` and the `spotify`/`statsbomb`/`nba` assets. Update `constants.py`. Keep the NBA `deps` chain for now (it's harmless) and revisit once concurrency is proven.

**Gate:** each `task ingest:*` runs. Most importantly, **run the concurrency check for real:** `task ingest:openf1` and `task dbt:build` at the same time, while `task cube:dev` and the dashboard are running. All must succeed.

### Phase 5 — Point the readers at the lake

- **Cube:** upgrade `@cubejs-backend/*` 1.6.65 → 1.8.x. `cube/cube.js` gets a `driverFactory` returning `DuckDBDriver({ databasePath: ':memory:', initSql: <attach READ_ONLY + USE lake> })`. `cube/.env` adds `CUBEJS_DB_DUCKDB_EXTENSIONS=ducklake,postgres` and drops the database path. Cube model YAML doesn't change.
- **Spotify dashboard:** move from `duckdb` (legacy package, last release 1.4.4) to `@duckdb/node-api@1.5.5-r.5`. Rewrite `src/lib/server/db.ts` (an in-memory instance + read-only ATTACH + `USE lake`), and keep the `query()` signature so `+page.server.ts` doesn't change. Fix any differences in returned value types (BigInt/DECIMAL handling) in one place.
- **Crypto dashboard:** remove its unused `duckdb` dependency (it only reads `live_data.json`).
- **nao:** upgrade to `nao-core` 0.3.25 in its isolated venv. In `nao_config.yaml`, switch to `type: ducklake`, `catalog: {type: postgres, host: localhost, database: data_world_lake, user: <you>, password: ""}`, with `data_path` from env and the `marts.nba_*` scope kept. Check `nao debug` and `nao sync`. (This is the deferred nao upgrade. Adding an LLM provider stays a separate decision.)

**Gate:** Cube Playground returns the existing `nba_*` and Spotify cubes; the dashboard renders; `nao sync` regenerates `nao/databases/**` — all **while a dbt build is running**.

### Phase 6 — Operations and docs

- **Maintenance:** a `task lake:maintain` task that runs the Phase 0 compaction/snapshot-expiry/cleanup calls, plus a weekly Dagster schedule for it.
- **CLAUDE.md:** rewrite the "DuckDB constraints" and "Lock contention" sections (the single-writer rule now only applies to the streaming files), update the Cube and nao sections, and add a short "Lake" section (catalog, data path, `USE lake`, Postgres must be running). Also update the README setup steps (`brew services start postgresql@17`, `task lake:init`) and the root and `cube/` `.env.example` files.
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
- **Elementary or incremental models may misbehave on DuckLake.** Phase 0 checks this before anything is committed.
- **dbt v2 is new (GA Sept 2026).** The DuckLake/Postgres-catalog combination isn't documented with an example, and v2 needs a separately installed (`dbc`) DuckDB driver for extensions, which adds a fourth DuckDB copy to keep in step with the Python, Node and Cube versions. Phase 0's decision gate means we only commit to v2 once it has been seen working end to end. Otherwise we fall back to the proven 1.x path.
- **Small-file growth** from OpenF1's per-session writes. The Phase 6 maintenance job handles it, and data inlining absorbs tiny writes in the meantime.

## Not in scope

Moving streaming into the lake (Phase 7), adding an LLM provider to nao, cloud or object storage, and Verano (already removed). The dbt v2 upgrade is in scope only if Phase 0's v2 track passes; otherwise it becomes a follow-up project.
