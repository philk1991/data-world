# Dataset Exploration: `statsbomb matches`
**Generated:** 2026-05-25  
**Tables analysed:** 1  |  **Total rows:** 3,464

---

## Table: `raw_statsbomb.raw_sb_matches`
**Rows:** 3,464  |  **Columns:** 17

### Column Profile

| Column | Type | Non-null | Null % | Distinct |
|---|---|---|---|---|
| match_id | INTEGER | 3,464 | 0.0% | ~3,788 |
| match_date | VARCHAR | 3,464 | 0.0% | ~1,318 |
| kick_off | VARCHAR | 3,459 | 0.1% | ~86 |
| competition_id | INTEGER | 3,464 | 0.0% | ~18 |
| competition_name | VARCHAR | 3,464 | 0.0% | ~20 |
| season_id | INTEGER | 3,464 | 0.0% | ~48 |
| season_name | VARCHAR | 3,464 | 0.0% | ~48 |
| home_team_name | VARCHAR | 3,464 | 0.0% | ~311 |
| away_team_name | VARCHAR | 3,464 | 0.0% | ~337 |
| home_score | INTEGER | 3,464 | 0.0% | ~14 |
| away_score | INTEGER | 3,464 | 0.0% | ~11 |
| match_status | VARCHAR | 3,464 | 0.0% | 1 |
| match_week | INTEGER | 3,464 | 0.0% | ~39 |
| competition_stage | VARCHAR | 3,464 | 0.0% | ~12 |
| stadium_name | VARCHAR | 3,454 | 0.3% | ~280 |
| referee_name | VARCHAR | 3,264 | 5.8% | ~412 |
| ingested_at | TIMESTAMP WITH TIME ZONE | 3,464 | 0.0% | ~73 |

### Numeric Column Stats

| Column | Min | Q25 | Median | Q75 | Max | Avg |
|---|---|---|---|---|---|---|
| match_id | 7,298 | 3,455,032 | 3,825,670 | 3,881,886 | 4,020,846 | 2,986,350 |
| competition_id | 2 | 9 | 11 | 37 | 1,470 | 79.8 |
| season_id | 1 | 27 | 27 | 42 | 315 | 51.7 |
| home_score | 0 | 1 | 1 | 2 | 13 | 1.60 |
| away_score | 0 | 0 | 1 | 2 | 9 | 1.26 |
| match_week | 0 | 5 | 14 | 25 | 38 | 15.5 |

> `match_date` range: `1958-06-24` → `2025-07-27`  
> `ingested_at` range: `2026-05-25 09:06:34+01` → `2026-05-25 09:06:58+01`

---

### Top Values — `competition_name` (20 distinct)

| Value | Count |
|---|---|
| Spain - La Liga | 868 |
| France - Ligue 1 | 435 |
| England - Premier League | 418 |
| Italy - Serie A | 381 |
| Germany - 1. Bundesliga | 340 |
| England - FA Women's Super League | 326 |
| International - FIFA World Cup | 147 |
| International - Women's World Cup | 116 |
| India - Indian Super league | 115 |
| Europe - UEFA Euro | 102 |
| Europe - UEFA Women's Euro | 62 |
| Africa - African Cup of Nations | 52 |
| United States of America - NWSL | 36 |
| South America - Copa America | 32 |
| Europe - Champions League | 18 |

### Top Values — `season_name` (48 distinct)

| Value | Count |
|---|---|
| 2015/2016 | 1,824 |
| 2020/2021 | 166 |
| 2018/2019 | 143 |
| 2021/2022 | 141 |
| 2023 | 122 |
| 2019/2020 | 120 |
| 2018 | 100 |
| 2022 | 95 |
| 2024 | 83 |
| 2019 | 52 |
| 2020 | 51 |
| 2014/2015 | 39 |
| 2003/2004 | 39 |
| 2011/2012 | 38 |
| 2017/2018 | 37 |

> **Notable skew:** 2015/2016 accounts for 1,824 rows (52.6% of all matches). This is StatsBomb's flagship free La Liga full-season dataset — models and aggregations should account for this imbalance when producing cross-season comparisons.

### Top Values — `competition_stage` (12 distinct)

| Value | Count |
|---|---|
| Regular Season | 2,961 |
| Group Stage | 328 |
| Round of 16 | 57 |
| Quarter-finals | 39 |
| Final | 36 |
| Semi-finals | 25 |
| 3rd Place Final | 6 |
| 1st Group Stage | 5 |
| Play-offs - Semi-Finals | 4 |
| Apertura | 1 |
| Championship - Final | 1 |
| 1st Round | 1 |

### Top Values — `match_status` (1 distinct)

| Value | Count |
|---|---|
| available | 3,464 |

> `match_status` is a constant — every row is `available`. Safe to filter or drop in staging.

### Top Values — `kick_off` (86 distinct)

> 86 distinct times; typical values follow clock-time patterns (15:00, 20:45, etc.). Stored as VARCHAR — cast to TIME in staging.

---

## Missing Data

| Table | Column | Null count | Null % |
|---|---|---|---|
| raw_sb_matches | referee_name | 200 | 5.8% |
| raw_sb_matches | stadium_name | 10 | 0.3% |
| raw_sb_matches | kick_off | 5 | 0.1% |

---

## Suggested dbt Models

### Staging

- `stg_statsbomb__matches` *(already exists as `stg_sb_matches`)* — match metadata with `match_date` cast to DATE, `kick_off` to TIME, `match_status` filter applied, and derived `match_result` / `goal_difference` columns

**Type casting issues to watch:** `match_date` and `kick_off` are both VARCHAR in the raw table. The staging model should cast them explicitly. `match_date` spans 1958–2025 so the range is valid; just needs `TRY_CAST` or `STRPTIME` rather than implicit cast.

### Potential marts

1. **`sb_competition_season_summary`** — grain: one row per `(competition_id, season_id)`. Answers: *how does scoring, home advantage, and match volume vary by competition and season?* Aggregates: match count, avg goals per game, home win %, draw %, away win %, highest-scoring match. Especially useful given the heavy 2015/16 La Liga weight.

2. **`sb_team_form`** — grain: one row per `(team_name, competition_id, season_id)`. Answers: *how did each team perform across a season?* Derives wins/draws/losses from home/away score columns, points total, goals for/against, GD. Requires unpivoting home vs away perspective — use a UNION ALL on home and away views.

3. **`sb_head_to_head`** — grain: one row per `(team_a, team_b)` sorted alphabetically. Answers: *what is the historical head-to-head record between two teams across all StatsBomb data?* Counts wins per side, draws, total goals. Useful for international tournaments (World Cup, Euro) where repeat fixtures exist.

---

## Relation to Existing dbt

### Already modelled in this domain

| Model | Schema | Description |
|---|---|---|
| `stg_sb_matches` | staging_statsbomb | Match metadata — filtered, casts scores, derives match_result and goal_difference |
| `stg_sb_competitions` | staging_statsbomb | Competition/season pairs |
| `stg_sb_events` | staging_statsbomb | All match events (one row per event) |
| `stg_sb_lineups` | staging_statsbomb | Player lineup data per match |
| `sb_match_summary` | marts | Match metadata + aggregate event counts |
| `sb_player_stats` | marts | Player statistics aggregated across all matches |

All four raw tables are sourced and staged. Two marts are built. The gap is **competition/season level** and **team form/standings** aggregations.

### Potential joins and enrichments

| Join | Key | Enables |
|---|---|---|
| `raw_sb_matches` ↔ `stg_recently_played` (Spotify) | `match_date` = `played_at::DATE` | Correlate which music was played on match days vs non-match days |
| `raw_sb_matches` ↔ `ohlcv_1h` (crypto) | `match_date` = candle `bucket::DATE` | Check if BTC/ETH volatility spikes on major match days (World Cup finals, etc.) — curiosity analysis |

These cross-domain joins are lightweight (date key) and exploratory rather than operational, but `sb_competition_stage = 'Final'` filtered to tournament matches makes for a clean, small dataset to test against.
