# Post-migration follow-ups

The DuckLake + dbt-oss migration (`plans/ducklake-migration-plan.md`, Phases 0–6) is complete and on `main` as of 21 Oct 2026. These are the items left open, roughly in the order they come due. Tick them off here as they're done.

## 1. Finish the StatsBomb backfill

- [ ] Confirm the first full ingest finished: all 3,961 matches have events and lineups.

At 941 of 3,961 on 21 Oct (morning), at roughly 10–16 matches a minute. The log is at `/tmp/p5_statsbomb.log`. The ingest is incremental, so if it stopped, run `task ingest:statsbomb` and it skips loaded matches. Retries now cover dropped connections, timeouts and 5xx errors, the cause of the overnight crash on 20 Oct.

Check:

```bash
task lake:sql SQL="select count(distinct match_id) from raw_statsbomb.raw_sb_events"
task lake:sql SQL="select count(distinct match_id) from raw_statsbomb.raw_sb_lineups"
```

Then run `task dbt:build` and check the `sb_*` marts.

## 2. Retire the old DuckDB file (due ~28 Oct 2026)

Wait for a week of normal use on the lake first. `spotify.duckdb` is the rollback point until then.

- [ ] Delete `data/spotify.duckdb`.
- [ ] Delete `scripts/migrate_schemas.py` and `scripts/migrate_to_lake.py`.
- [ ] Remove the `migrate:schemas` and `lake:migrate` tasks from `Taskfile.yml`.
- [ ] Remove the `spotify.duckdb` line from the README project tree, the "Pre-lake database" paragraph in CLAUDE.md, and the reference in the nba asset docstring (`orchestration/dagster_data_world/assets/nba.py`).
- [ ] `git grep -n "spotify.duckdb\|DUCKDB_PATH"` should then only match `plans/` and `CRYPTO_DUCKDB_PATH`.

## 3. Tidy up the migration branch

- [ ] Delete `ducklake-migration` locally and on GitHub (`git branch -d ducklake-migration && git push origin --delete ducklake-migration`). `main` contains all of it.
- [ ] Optional: remove the leftover ADBC driver from Phase 0 in `~/Library/Application Support/ADBC/Drivers` (dbt uses the one in `.venv/etc/adbc/drivers`).

## 4. Check the weekly maintenance is working

- [ ] After the first Sunday 05:00 run of `lake_maintenance` in Dagster, check its logs for the before and after numbers.
- [ ] Watch `task lake:status` for a couple of weeks. The snapshot count should level off (roughly a week of commits) instead of growing without limit.

If the lake still grows, consider a shorter retention (`RETAIN`) or running maintenance after each big ingest.

## 5. nao decisions

- [ ] **Pick an LLM provider.** `nao chat` needs `llm:` in `nao/nao_config.yaml`. nao-core 0.3.25 supports `ollama`, which makes a free local model possible. The alternative is a hosted provider (key in `nao/.env`).
- [ ] **Try merging nao into the main venv.** It was isolated because nao-core 0.0.x pulled protobuf 7, which breaks Dagster. 0.3.25 doesn't install protobuf at all. Test in a scratch venv with `requirements.txt` plus `nao-core[duckdb]==0.3.25`, then check that `pip check`, `dbt build` and Dagster validation still pass. If it works, drop `nao/.venv` and update `nao:*` tasks and CLAUDE.md.
- [ ] Optional: nao 0.3.26 is out. Upgrade together with its DuckDB pin (keep `duckdb==1.5.5` unless every other client moves too).

## 6. OpenF1 stints data-quality tests

Three tests on `stg_openf1__stints` fail on the source data: `not_null` on `compound` (93 rows) and `tyre_age_at_start` (31 rows), and `accepted_values` on `compound` (1 row). This predates the migration.

- [ ] Look at the failing rows (`/test-failures openf1`) and decide whether to fix them in staging (e.g. map unknown compounds to `UNKNOWN`), relax the tests to `warn`, or filter the affected stints.

## 7. Optional: Phase 7, streaming into the lake

From the migration plan. Only once maintenance has proven it copes with many small commits (item 4).

- [ ] Crypto and payments consumers write to the lake instead of their own DuckDB files, committing in batches.
- [ ] The crypto sensor polls the lake's snapshots instead of `crypto_raw.duckdb`.
- [ ] Retire `setup:streaming-dbs`, the `crypto_raw`/`payments_raw` attaches in `dbt/profiles.yml`, and possibly the JSON sidecar.
