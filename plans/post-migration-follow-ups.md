# Post-migration follow-ups

The DuckLake + dbt-oss migration (`plans/ducklake-migration-plan.md`, Phases 0–6) is complete and on `main` as of 21 Oct 2026. These are the items left open, roughly in the order they come due. Tick them off here as they're done.

## 1. Finish the StatsBomb backfill (done)

- [x] Confirm the first full ingest finished: all 3,961 matches have events and lineups.

Confirmed 2 Nov: `raw_sb_events`, `raw_sb_lineups` and `raw_sb_matches` all cover 3,961 matches, and so does `marts.sb_match_summary`, so the marts have been rebuilt on the full data.

At 941 of 3,961 on 21 Oct (morning), at roughly 10–16 matches a minute. The log is at `/tmp/p5_statsbomb.log`. The ingest is incremental, so if it stopped, run `task ingest:statsbomb` and it skips loaded matches. Retries now cover dropped connections, timeouts and 5xx errors, the cause of the overnight crash on 20 Oct.

Check:

```bash
task lake:sql SQL="select count(distinct match_id) from raw_statsbomb.raw_sb_events"
task lake:sql SQL="select count(distinct match_id) from raw_statsbomb.raw_sb_lineups"
```

Then run `task dbt:build` and check the `sb_*` marts.

## 2. Retire the old DuckDB file (done 21 Oct 2026)

Done early, on 21 Oct. Before deleting, every `raw_*` table in `spotify.duckdb` was checked against the lake: row counts matched, except `raw_spotify.raw_top_artists` (129 old, 128 lake), which is a full-replace table that has a newer snapshot in the lake. `scripts/` was left empty, so it was removed from the README tree too.

- [x] Delete `data/spotify.duckdb`.
- [x] Delete `scripts/migrate_schemas.py` and `scripts/migrate_to_lake.py`.
- [x] Remove the `migrate:schemas` and `lake:migrate` tasks from `Taskfile.yml`.
- [x] Remove the `spotify.duckdb` line from the README project tree, the "Pre-lake database" paragraph in CLAUDE.md, and the reference in the nba asset docstring (`orchestration/dagster_data_world/assets/nba.py`).
- [x] `git grep -n "spotify.duckdb\|DUCKDB_PATH"` should then only match `plans/` and `CRYPTO_DUCKDB_PATH`.

## 3. Tidy up the migration branch

- [x] Delete `ducklake-migration` locally and on GitHub (`git branch -d ducklake-migration && git push origin --delete ducklake-migration`). `main` contains all of it.
- [ ] Optional: remove the leftover ADBC driver from Phase 0 in `~/Library/Application Support/ADBC/Drivers` (dbt uses the one in `.venv/etc/adbc/drivers`).

## 4. Check the weekly maintenance is working

- [ ] After the first Sunday 05:00 run of `lake_maintenance` in Dagster, check its logs for the before and after numbers.
- [ ] Watch `task lake:status` for a couple of weeks. The snapshot count should level off (roughly a week of commits) instead of growing without limit.

If the lake still grows, consider a shorter retention (`RETAIN`) or running maintenance after each big ingest.

Progress so far:

- **23 Oct, manual run:** nothing to expire yet (the oldest snapshot was from 21 Oct, inside the 7-day retention). Snapshots went from 8,920 to 8,923, and disk use *rose* from 872 MB to 1,580 MB, because merged files sit beside the originals that retained snapshots still reference.
- **25 Oct and 1 Nov, scheduled runs:** neither fired. The `dagster dev` started on 23 Oct was still up, but its code server had died (gRPC UNAVAILABLE), so the schedule never ran.
- **1 Nov, manual run of `lake_maintenance_job`:** the first run that reclaimed anything. Snapshots went from 9,423 to 502, disk from 1,983 MB to 1,389 MB.
- **2 Nov:** 600 snapshots, 1.4 GB. Dagster isn't running, so restart it (`task dagster:dev`) before Sunday 8 Nov and check that the scheduled run fires. The first box stays open until a scheduled run has worked.

## 5. nao decisions

- [ ] **Pick an LLM provider.** `nao chat` needs `llm:` in `nao/nao_config.yaml`. nao-core 0.3.25 supports `ollama`, which makes a free local model possible. The alternative is a hosted provider (key in `nao/.env`).
- [x] **Try merging nao into the main venv.** It was isolated because nao-core 0.0.x pulled protobuf 7, which breaks Dagster. 0.3.25 doesn't install protobuf at all. Test in a scratch venv with `requirements.txt` plus `nao-core[duckdb]==0.3.25`, then check that `pip check`, `dbt build` and Dagster validation still pass. If it works, drop `nao/.venv` and update `nao:*` tasks and CLAUDE.md.
- [x] Optional: nao 0.3.26 is out. Upgrade together with its DuckDB pin (keep `duckdb==1.5.5` unless every other client moves too).

Done 2 Nov, together: nao-core 0.3.31 is in `requirements.txt` and lives in `.venv`. The only conflict was `python-dotenv` (nao needs >=1.2.1), now pinned to 1.2.4. Tested on a copy of `.venv` first: `pip check` clean, Dagster validates (65 assets), `dbt parse` ok, `nao debug` and `nao sync` ok. Protobuf stays at 6.33.6 and Dagster at 1.13.26. `nao/.venv` and `task nao:install` are gone.

Heads-up for the next Dagster upgrade: `requirements.txt` doesn't pin Dagster, and a fresh resolve pulls Dagster 1.13.28 with protobuf 7 (Dagster now allows <8, and `grpcio-health-checking` 1.85 requires 7). That comes from Dagster's own dependencies, not nao.

## 6. OpenF1 stints data-quality tests

Three tests on `stg_openf1__stints` fail on the source data: `not_null` on `compound` (93 rows) and `tyre_age_at_start` (31 rows), and `accepted_values` on `compound` (1 row). This predates the migration.

- [x] Look at the failing rows (`/test-failures openf1`) and decide whether to fix them in staging (e.g. map unknown compounds to `UNKNOWN`), relax the tests to `warn`, or filter the affected stints.

Done 21 Oct: all three are now `severity: warn`, and `TEST_UNKNOWN` (132 stints, the one failing value) is an accepted compound. `dbt test --select stg_openf1__stints` gives 6 passes and 2 warnings.

## 7. Optional: Phase 7, streaming into the lake

From the migration plan. Only once maintenance has proven it copes with many small commits (item 4).

- [ ] Crypto and payments consumers write to the lake instead of their own DuckDB files, committing in batches.
- [ ] The crypto sensor polls the lake's snapshots instead of `crypto_raw.duckdb`.
- [ ] Retire `setup:streaming-dbs`, the `crypto_raw`/`payments_raw` attaches in `dbt/profiles.yml`, and possibly the JSON sidecar.

Notes from scoping it on 22 Oct (parked until item 4 has the results of Sunday's run; the 1 Nov manual run meets that, but a scheduled run that fires is better proof):

- Both streaming files are empty placeholders, so no data has to be copied.
- The consumers write after every 100 messages or 1 second idle. On the lake that's a snapshot per write, so commit on a timer (e.g. every 30s or 1,000 rows), one `transaction()` per write, and commit the Kafka offset only after the lake commit.
- Crypto sensor: watch the lake's latest snapshot touching `raw_crypto` rather than counting rows.
- Keep the JSON sidecar: the dashboard polls it every few seconds, which would only add catalog read load if pointed at the lake.
- Sources: `database: crypto_raw`/`payments_raw` in the two `sources_*.yml` files drop out (they become lake schemas).
