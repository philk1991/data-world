# NBA analytics: a staff-level analytics engineering project

Status: Phases 0–2 done on branch `nba-staff-ae-phase-1` (10 Nov 2026); Phase 3 next. Decisions: `plans/adr/0001`–`0005`.

## Goal

Someone asking an NBA question gets the same number from the dbt marts, from Cube and from nao, and can trust that number. Today they don't: the review below found the same question answered three different ways, and one Cube measure that is badly wrong.

The project has two parts. First, fix what the review found. Second, settle the boundary between dbt and Cube so the drift can't come back. The second part is the staff-level work: making an architecture decision, writing it down, migrating without breaking consumers, and proving the result with tests that span every tool.

**Done when:**

- A golden-question suite (Phase 5) passes for the same answer from the mart, from Cube and from nao. It runs in CI and in the daily Dagster job.
- No rate or ratio formula is written in more than one place across dbt, Cube and nao.
- Every finding in Part 1 is fixed or has a recorded decision.

---

## Part 1: Review findings (6 Nov 2026)

These are read-only queries against the lake and the running Cube server. All 270 NBA data tests passed (267 pass, 3 warn), but none of them caught the problems below.

### The same question, different answers

| Question | dbt / nao | Cube | Expected |
|---|---|---|---|
| LeBron career points | 52,142 (`nba_player_career_stats`, includes playoffs) | 53,916 (no filter: adds preseason and All-Star) | 43,522 in the regular season, the usual meaning of "career points" |
| Oscar Robertson triple-doubles | 0 (`nba_player_advanced_career`) or 187 (`nba_player_game_stats`) | not available | 187 competitive, 179 regular season |
| Jason Kidd triple-doubles | 105 or 118 | not available | 118; the career mart misses games with no advanced box score |
| Top qualified true shooting season | sensible | Art Spector 1946-47: 6,136% | Cube is wrong |
| Bob Pettit 1958-59 TS% | .523 | .855 | Cube is wrong |
| Bill Russell 1964-65 TS% | .471 | .551 | Cube is wrong |
| Points by team, 2021-22 | team available in `nba_player_season_advanced` | 584 players / 258,712 points under a null team | Cube is wrong |
| Luka Doncic PPG 2025-26 | 33.0 (regular season) | 32.4 (no filter) | 33.0 |
| How many players? | 4,958 with a competitive game | 6,969 (`nba_players_dim.count`, includes players with no games and duplicate ids) | 4,958 |

### Findings to fix

1. **Cube's true shooting is wrong before about 1980.** The measure keeps a whole player-season's points but only the attempts from games that recorded them. The median qualified season is out by 148 points in the 1940s, 58 in the 1950s and 5.7 in the 1960s, and 492 qualified seasons show over 100%. The cause is that Cube re-implements `nba_ts` by hand, and the inputs it can see are season totals. From 1990 on it matches dbt exactly. `effective_field_goal_pct` has the same weakness, off by up to 0.013.
2. **`primary_team_id` and `player_team_id` are null for 2021-22.** `nba_player_season_stats` and `nba_player_game_stats` read the raw team id instead of `int_nba_player_games`, which recovers it. That leaves 26,018 game rows with no team. The two season marts also break ties differently (`MODE` vs `ARG_MAX`), so they disagree on 54 further seasons.
3. **No scope is defined.** Cube sums every game type, the career mart sums competitive games, and fans mean the regular season. RULES.md patches this for nao only.
4. **Pre-1955 seasons are silently incomplete.** The source has only the 30 current franchises, so games against defunct teams don't exist. 1946-47 has 18 games across 3 teams, and full schedules only start in 1954-55. As a result, George Mikan shows 8,208 points including playoffs, and early players can qualify on 10 of 12 team games. The decision log's claim that player logs "cover every game from 1946-47" is wrong.
5. **2024-25 has six bad regular-season games.** Four are missing upstream (1,226 of 1,230 games). Two more are 0–0 with no player box but still count as a result, and the raw `winner` is wrong on one of them (22400627: Utah won 128–112 by the team box and play-by-play, but `winner` says Washington). After dropping the 0–0 games, 10 teams show 81 games and SAS 80. *Investigated 10 Nov 2026:* the gap is still in the latest Kaggle version (542) and every cached version since 19 Oct, so re-ingesting doesn't help. All six games are in the play-by-play. Decision: document it as an upstream gap (doc block `nba__upstream_gap_2024_25`, Cube and nao caveats) and report it on Kaggle rather than repair it. Nothing tests for positive scores or complete closed seasons. Separately, four 2026-27 games have no player box, and Mike Farmer's 1962-63 playoff FT% is 1.118.
6. **Double-doubles have two definitions.** The career mart uses the NBA's 1996+ flag; the game mart computes from the box score for every era. League-wide that is 2,184 vs 3,763 triple-doubles.
7. **nao's context contains errors.**
   - RULES.md says `marts.<table>` fails, but `docs/nba/nba_marts.md` tells nao to use it.
   - Both say ratings are 0–1 fractions; `offensive_rating` is about 115.
   - RULES.md says advanced metrics start around 1996; they now cover all eras.
   - The `total_minutes >= 500` qualification rule lives only in prose and isn't scaled to short seasons. In 2024-25, 138 of the 368 players over 500 minutes aren't qualified.

### Smaller findings

- **Duplicated logic:**
  - the competitive game-type list is hard-coded in 6 models;
  - the `season_label` expression in 10;
  - the coverage years (1964, 1973, 1977, 1979) across 9 files;
  - the TS formula is re-typed in `nba_player_clutch_stats`;
  - the league TS CTE is duplicated in two marts;
  - the name fallback is repeated in three.
- **Older marts skip the intermediates.** Seven marts read staging directly. That split caused finding 2 and the name inconsistencies.
- **Tests are thin in places:**
  - no `relationships` tests;
  - no source freshness check;
  - no schedule-completeness test;
  - unit tests cover only 8 of 17 marts and 2 of 5 intermediates. Clutch, shot zones, form and double-doubles have none.
- **Governance gaps:**
  - no CI or pre-commit, so `dbt:docs:check` and `cube:docs:check` only run when someone remembers;
  - no exposures or contracts;
  - `task nao:sync` isn't in Dagster, so nao's context can lag the daily build;
  - `formula_version` is missing from `nba_player_game_stats`, which uses Game Score.
- **Modelling issues:**
  - marts round values, and Cube's `max_*` measures then read the rounded figures;
  - `current_full_name` shows the SuperSonics as the Thunder (no team-by-season dimension);
  - `usage_pct`, `assist_pct` and `rebound_pct` mean the NBA feed's value in the game mart but the box estimate in the season marts;
  - `stg_nba_team_statistics_extended` has no downstream models;
  - NBA naming doesn't follow the project conventions (`stg_nba_games`, not `stg_nba__games`), and `stg_nba_play_by_play` goes well beyond staging;
  - the dbt project is still called `spotify`.
- **Documentation is the strongest area:** all 484 mart columns have comments, and the doc-block and Cube drift checks pass. The weak spots are `nba_marts.md` duplicating dbt by hand and thin staging YAML.

### Checked and clean

- **Rollups:** game → season → career reconciles exactly across 51,536 rows.
- **Team records:** `nba_team_season_summary` and `nba_team_advanced_profile` agree on all 1,717 team-seasons, and head-to-head matches on all 870 pairs.
- **Scores and stints:** scores match across 71,488 games, and stints sum to seasons.
- **League and team maths:** the two league TS calculations agree. All SRS runs converged. Summed-game and season net rating differ by more than rounding on only 6 of 1,086 team-seasons.
- **Keys:** no orphan keys apart from All-Star teams.
- **Historic records:** 73–9, Wilt's 100 and 50.4, and the Kareem, Malone and Jordan totals look right.

---

## Part 2: Target design, splitting work between dbt and Cube

### 2.1 What the industry does

The sources agree on one principle and disagree on one trade-off.

**Where they agree: store additive parts, compute ratios at query time.**

- **Kimball:** ratios are "completely non-additive"; "store the fully additive components" and sum them before computing the ratio, a step "often done in the BI layer or OLAP cube".
- **dbt Labs:** "Prefer computing values in measures and metrics when possible as opposed to in frozen rollups", and "The more we pre-compute and 'freeze' into place, the less flexible our data is." Ratio metrics are defined in the semantic layer from simple metrics, never stored as mart columns.
- **Cube:** dbt projects build "normalized data marts for the semantic layer", and Cube adds "measures, joins, and pre-aggregations" on top.

Finding 1 is exactly the failure this rule prevents. Cube received a frozen season total and had no way to rebuild a correct ratio from it.

**Where they disagree: wide tables or a star schema?**

- **Normalised star** (dbt with MetricFlow, Cube, LookML): the semantic layer does the joins, so pre-joining in dbt is redundant. dbt: "Prefer normalization when possible to allow MetricFlow to denormalize dynamically."
- **Wide tables** (Lightdash): "with today's columnar warehouses, wide and flat often performs better". Keep the star upstream, then "combine the models into wide tables that you surface in the BI layer". This suits self-serve users who can't navigate ten joins.
- **Both camps** keep a star schema upstream. The disagreement is only about what the consuming tool sees.

**Where Cube is heading: views as the published interface.**

- "Cubes should remain private; set `public: false` for all cubes. Only views can be exposed."
- "AI agents query your data model through views," and "Smaller, focused views are easier to navigate and lead to better AI results."
- Agent guidance goes in `meta.ai_context` on views or members (it is ignored at cube level).
- View measures may combine members of different cubes with `multi_stage: true`, which aggregates each part before dividing.

**Why it matters for AI agents.** A semantic layer gets more questions right, but only within what has been modelled.

- dbt's 2026 benchmark: within scope, 98–100% with the semantic layer vs 84–90% for text-to-SQL.
- On the unmodelled schema overall: 72.7% vs 64.5%, with 0% from the semantic layer on questions needing too many joins.
- Its key point: "the Semantic Layer tells you it can't answer. It never returns invalid data. Text-to-SQL will cheerfully give you a wrong number."
- AtScale and Cube report similar gains, but they are vendors.

That explains how nao should work. Defined metrics go through the semantic layer, and SQL over the marts stays as a clearly labelled fallback for exploration.

**Open-source landscape.** dbt Labs moved MetricFlow to Apache 2.0 on 14 Oct 2025 and joined the Open Semantic Interchange (now Apache Ossie). Secondary sources say Cube imports dbt models but not dbt metrics, and whether a working Cube↔Ossie converter exists is disputed. Treat portability between MetricFlow and Cube as unproven.

**What the local spike showed (10 Nov):**

- dbt-oss 2.0.8 rejects MetricFlow's legacy `semantic_models:` YAML with a deprecation warning.
- It accepts the newer format attached to a model (`semantic_model: enabled`, `derived_semantics`, model-level `metrics`). It then writes a `semantic_manifest.json` that includes a ratio metric.
- nao 0.3.31 can run a MetricFlow layer natively (`semantic_layer:` in `nao_config.yaml`, extra `nao-core[semantic-layer]`, DuckDB dialect).
- Not yet tested: whether nao's pinned MetricFlow (>=0.213,<0.214) reads the manifest dbt-oss writes. A time spine model would also be needed.

### 2.2 Options

**A. Thick marts, thin Cube (formalise today's setup).** dbt pre-computes every metric at fixed grains: season, career, team-season. Cube passes columns through and adds simple sums. nao reads the same marts.

- *For:* the least work. SQL users and nao see final numbers. Lightdash's wide-table approach is the closest industry match.
- *Against:* every new grain needs a new mart. A frozen ratio can't be re-aggregated, which is finding 1. Cube still needs its own formulas for any slice the marts don't pre-compute, so drift continues. This is the pattern dbt calls "frozen rollups".
- *Fit:* fine for a dashboard with fixed questions. It doesn't meet the goal here.

**B. Components in dbt, metrics in Cube (recommended).** dbt marts hold atomic-grain facts with additive components (`ts_points`, `ts_fga`, `ts_fta`, `usage_plays`, `usage_opportunity`, …), conformed dimensions, and a small set of non-additive analytic facts at their natural grain (SRS, Oliver ratings). Cube owns joins, every rate (sum over sum), scope and qualification measures, multi-stage calculations (rank, share of total, vs league), and views as the only published interface. nao answers metric questions through the Cube MCP server and uses SQL on the marts only for exploration.

- *For:* one definition per metric, correct at any grain. Matches Kimball, dbt and Cube's own guidance. Cube already serves the dashboards and Claude via MCP. Most of the dbt work is already done, because `int_nba_player_game_context` and `int_nba_player_stints` already compute numerator/opportunity pairs.
- *Against:* nao doesn't support Cube natively, so it would rely on MCP and the model following a "use Cube first" rule. Some metrics can't be split into sums and stay in dbt, so the boundary needs a written rule. Cube multi-stage measures aren't accelerated by pre-aggregations (irrelevant at this data size).
- *Fit:* strong.

**C. MetricFlow in dbt as the single source, Cube kept or retired.** Metrics live in dbt YAML. nao queries them natively, and dbt CI validates them.

- *For:* definitions sit next to the models and ship with every dbt build. Native nao support, open source, and aligned with Ossie.
- *Against:* Cube can't import dbt metrics, so keeping Cube duplicates every definition, which is the problem this project exists to solve. Retiring Cube loses the REST API, the MCP server and the dashboard path, because open-source MetricFlow is a SQL compiler, not a server. dbt-oss's new YAML and MetricFlow 0.213 compatibility is unverified.
- *Fit:* the right answer if Cube is ever dropped. Keep it open as a time-boxed spike (Phase 7).

**D. Option B, with Cube files generated from dbt metadata.** Same runtime split as B, but authors declare components and metrics in dbt `config.meta`, and a script generates the Cube YAML. This extends `cube/scripts/sync_dbt_descriptions.py` from descriptions to measures. It is the Lightdash idea of "metrics in dbt YAML" with Cube as the engine.

- *For:* one place to write things, with the dbt docs, the Cube model and nao's context all generated from it.
- *Against:* it builds a home-grown compiler. Worth it only once the hand-written Cube model has stabilised.
- *Fit:* a good Phase 6 follow-on to B, not a starting point.

| | A: thick marts | B: components + Cube metrics | C: MetricFlow | D: B, generated |
|---|---|---|---|---|
| One definition per metric | no | yes | only if Cube retired | yes |
| Correct when re-aggregated | no | yes | yes | yes |
| Dashboards / Cube MCP keep working | yes | yes | only if Cube kept (duplicates) | yes |
| nao support | SQL only | MCP | native | MCP |
| Effort | low | medium | medium to high | high |
| Industry alignment | Lightdash wide tables | Kimball, Cube, dbt principle | dbt / Ossie direction | Lightdash-style authoring |
| Staff-level learning | low | high | high | high |

**Recommendation: B now, with D as a later step and C as a spike.** B is the only option that keeps every consumer working and leaves exactly one definition per metric. It also makes the fewest changes to what already works.

### 2.3 Where things live

| Concern | Layer | NBA example |
|---|---|---|
| Rename, cast, turn zero-filled stats back into nulls | dbt staging | `null_if_unrecorded`, `nba_minutes` |
| Entity resolution and game-grain enrichment | dbt intermediate | team recovery, opponent pairing, player-sum fallback |
| Per-game opportunity denominators | dbt intermediate → fact | `usage_opportunity`, `assist_opportunity`, `on_court_share` |
| Atomic facts with additive components | dbt marts (facts) | player-game, team-game, shot event |
| Row-level business attributes | dbt marts | `is_competitive`, `is_neutral_site`, `is_double_double`, `coverage_tier` |
| Conformed dimensions | dbt marts (dims) | player, team, team-season (name as of that season), season, game type |
| Non-additive analytic facts (needs iteration, a model or a window) | dbt marts, tagged non-additive | SRS, Oliver ratings, as-of form, league baselines |
| Every ratio, rate and per-game average | Cube measure (sum over sum) | TS%, eFG%, PPG, win%, usage%, net rating |
| Default scope | Cube measure `filters` and views | `career_points` = regular season only |
| Qualification at query time | Cube segment, on a dbt flag | `qualified` segment on `is_qualified` |
| Rank, share of total, vs league, period over period | Cube multi-stage measures | `field_goal_pct_vs_league` |
| Display rounding and formats | Cube `format`, consumer | never `ROUND` in a mart |
| Published interface for BI, MCP and agents | Cube views (cubes private) | `player_season`, `team_season`, `game` |
| Agent instructions | Cube `ai_context`, plus RULES.md generated from it | grain, scope, coverage caveats |
| Ad-hoc exploration | nao SQL on marts, labelled as unofficial | "which arenas had the most overtime games" |

**Rule for the boundary:** if a value can be rebuilt from additive columns by a sum over sum, dbt stores the parts and Cube owns the ratio. If it can't, dbt computes it at its natural grain, tags it `meta.additive: false`, and Cube exposes it as a dimension or a non-aggregating measure that is never summed or averaged across rows.

### 2.4 Worked examples

- **True shooting.** `nba_player_game_stats` gains `ts_points`, `ts_fga` and `ts_fta`, set only where both attempt counts were recorded. Cube: `true_shooting_pct = SUM(ts_points) / (2 * (SUM(ts_fga) + 0.44 * SUM(ts_fta)))`. This is the same at game, season, career or any filter, and fixes finding 1 by construction. The 0.44 lives in Cube only; dbt's `nba_ts` macro remains for the non-additive marts.
- **Career points.** Cube measures `points` (no filter), `regular_season_points` and `competitive_points`, using measure `filters` on `is_competitive` / `game_type`. The `player_career` view publishes the agreed default from Phase 0.
- **Usage, assist, rebound, steal and block %.** These are already numerator/opportunity pairs per game in `int_nba_player_game_context`. Expose them on the player-game fact and divide in Cube. `nba_player_stint_advanced` and `nba_player_season_advanced` then become checks against Cube rather than sources.
- **Oliver individual ratings.** Not additive: they are computed from stint totals. They stay in dbt at stint grain (`additive: false`). The season value remains points produced over individual possessions, both of which are additive, so Cube can still own the season ratio.
- **SRS.** It is solved by iteration, so it stays in dbt at team-season grain and is exposed as a team-season dimension.
- **Qualification.** `is_qualified` (70% of team games) is a row attribute and stays in dbt. The 500-minute rule for advanced stats becomes a second, scaled dbt flag, and Cube exposes both as segments. RULES.md stops defining thresholds.
- **Double-doubles.** One box-score definition on the game fact; Cube counts it. The career mart's NBA-flag version is retired.
- **Team names.** A new team-season dimension carries the name as of that season. `nba_team_dim` keeps the current identity.

### 2.5 Shape of the marts

The atomic facts already exist (`nba_player_game_stats`, `nba_team_game_stats`), so the reshaping is smaller than it sounds:

- add components and flags to the two game facts, plus a shot-event fact for zones and clutch;
- add the dimensions: `nba_seasons_dim`, `nba_game_types_dim`, `nba_team_seasons_dim`;
- keep the non-additive marts (team advanced profile, SRS, form, baselines, stint advanced), tagged;
- move `nba_player_season_stats`, `nba_player_career_stats`, `nba_player_season_advanced`, `nba_player_advanced_career` and `nba_team_season_summary` in Cube onto the facts, as dbt advises: "build in parallel so you can audit … and deprecate old marts gracefully."

Whether the rollup marts stay as convenience tables for SQL users (reconciled to Cube by test) or are retired is decision 0.4.

---

## Part 3: Plan

### Phase 0: decisions, written up as short ADRs in `plans/adr/` (done 10 Nov)

- [x] 0.1 Career = regular season by default, playoffs as the alternative, one row each so they add up; play-in and Cup final count toward neither (ADR 0001).
- [x] 0.2 Option B: components in dbt, metrics in Cube (ADR 0002).
- [x] 0.3 Seasons before 1954-55 excluded from careers, Cube and nao's defaults; kept and tagged in game and season marts (ADR 0003).
- [x] 0.4 Rollup marts kept as convenience tables, reconciled by construction; `nba_<entity>` names kept (ADR 0004).
- [x] 0.5 nao: Cube for defined metrics, SQL for exploration, SQL answers say so (ADR 0005).

### Phase 1: correctness fixes from the review (done 10 Nov)

- [x] `int_nba_player_games` now covers every game type (`is_competitive` flag), nulls impossible shooting pairs and owns the double-double definition. `nba_player_season_stats` and `nba_player_game_stats` are built on it: teams recovered (2021-22 has no null teams), one primary-team rule (most games, then minutes, then lower id), shared with `nba_player_season_advanced`.
- [x] Career marts rebuilt per ADR 0001 and 0003; career double-doubles counted from the box score (Oscar Robertson 179, Kidd 107, matching the game mart).
- [x] Cube TS/eFG fixed properly rather than as a stopgap: the season mart exposes `ts_*` / `efg_three_pointers_made`, and Cube divides their sums (Pettit 1958-59 .523, matching dbt).
- [x] Data tests: `assert_nba_played_games_have_scores`, `assert_nba_closed_seasons_complete` (known exceptions 1955, 1956, 2012, 2019, 2024 with reasons), `assert_nba_player_shooting_is_possible`, `assert_nba_career_reconciles_with_seasons`. 0–0 no-result games dropped in staging; 2024-25's four missing games recorded as an upstream gap.
- [x] nao: RULES.md corrected (units, coverage, default scope, `is_qualified` replaces the 500-minute rule); `nao/docs/nba/nba_marts.md` generated from dbt by `task nao:sync`.
- [x] Decision log corrected on pre-1955 coverage; field guide updated for the career grain.

Acceptance met: every row of the Part 1 answer table now gives the expected value from the marts and from Cube (LeBron regular-season career 43,522 in both; Doncic 2025-26 33.0; 4,958 players; 2021-22 points grouped by real teams).

### Phase 2: conformed dimensions and flags (done 10 Nov, except where noted)

- [x] `nba_seasons_dim`: label, `is_current`, `coverage_tier`, `is_in_coverage`, games and teams per season.
- [x] `nba_game_types_dim` with `is_competitive`, `is_career`, `counts_toward_standings`; `is_competitive` on the player game and season marts.
- [x] `nba_team_seasons_dim` with the name, city and abbreviation as of that season (abbreviations trimmed in staging).
- [x] `dbt/macros/nba_scope.sql`: season label (was copied in 10 models), competitive and career game types (6), coverage years (9 files), the coverage cutoff var.
- [x] `relationships` tests on the player season, career and team-season marts. Still to add: team-game facts → `nba_team_seasons_dim` (needs a two-column relationship test).

### Phase 3: components in dbt, metrics in Cube

Already started: Cube filters to seasons from 1954-55 through `nba_seasons_dim`, has `regular_season` / `playoffs` / `career` / `completed_seasons` / `competitive` / `has_competitive_games` segments, and computes TS% and eFG% from components.

Found while doing Phases 1–2, to settle here:

- [ ] **Shooting leaderboards need an attempts minimum.** With `qualified` + `completed_seasons`, the top true shooting seasons are low-volume centres who qualify on games but take few shots. Decide a scaled attempts threshold (Basketball-Reference uses one per stat) and put it in dbt as a flag, not in Cube or RULES.md.
- [ ] Career measures in Cube with measure-level `filters` (regular-season and playoff points), so a career needs no segment.

- [ ] Add additive components to the player-game and team-game facts. Add a shot-event fact for zones and clutch.
- [ ] Remove `ROUND` from marts; set display formats in Cube.
- [ ] Cube: set cubes to `public: false`. Build `player_game`, `player_season`, `player_career`, `team_game`, `team_season` and `league_season` views. Add rates as sum over sum, scope measures, segments and multi-stage vs-league measures. Add `ai_context` per view.
- [ ] Tag non-additive marts `meta.additive: false` and expose them as dimensions.
- [ ] Reconciliation tests: each retired or kept rollup mart equals the Cube result within rounding.

Acceptance: no rate formula appears in more than one of dbt, Cube and nao (a grep in CI).

### Phase 4: route nao through Cube

- [ ] Register the Cube MCP server in `nao_config.yaml` (`mcp: json_file_path`).
- [ ] Generate the RULES.md table section and the metric list from the Cube `/meta` output and dbt, instead of maintaining them by hand.
- [ ] Re-run the Curry shot-zone and clutch questions from `plans/nao-hosted-model-plan.md`. Pairs with that plan's model move: a 14B local model is unlikely to choose tools reliably.

### Phase 5: golden questions

- [ ] 15–25 questions with expected answers: the Part 1 table, 2015-16 Warriors, Pettit TS%, season leaders, 2021-22 team totals, home win rate excluding neutral sites.
- [ ] A dbt singular test per question against the marts, a pytest against the Cube REST API, and `nao test` cases. nao 0.3.31 has `nao test` with pass@k and numeric tolerances.
- [ ] Run in CI and after `nba_pipeline` in Dagster.

### Phase 6: governance

- [ ] Investigate a DuckLake commit stall seen on 10 Nov: two small tables (`nba_players_dim`, `nba_team_head_to_head`) took 12 minutes in one `dbt build` while waiting on each other's commits; the same build took about a minute before and after. Check the retry settings in `profiles.yml` and `lake.py` under 4 threads.

- [ ] CI (GitHub Actions or pre-commit): `dbt parse`, `dbt:docs:check`, `cube:docs:check`, SQLFluff, unit tests, and the formula-duplication grep.
- [ ] dbt exposures for Cube views, nao and the field guide.
- [ ] Contracts on the published facts and dimensions.
- [ ] Source freshness for `raw_nba`; a latest-game-date check.
- [ ] `nao:sync` and `docs:nba-guide` as Dagster steps after the NBA dbt build.
- [ ] Unit tests for the clutch, shot-zone, form and double-double logic, and for the `nba_minutes` and `null_if_unrecorded` macros.
- [ ] Optional, option D: generate Cube measures from dbt `meta`, extending `sync_dbt_descriptions.py`.

### Phase 7: MetricFlow spike, time-boxed to a day

- [ ] Install `nao-core[semantic-layer]` in a throwaway venv and check whether MetricFlow 0.213 reads dbt-oss 2.0.8's new-style `semantic_manifest.json`. Add a time spine model.
- [ ] Run three golden questions through `execute_semantic_query`.
- [ ] Write up whether option C would be viable if Cube were ever dropped, and check whether Cube has a working Ossie importer yet.

### What to show for staff level

- ADRs for every Phase 0 decision, each with options considered, the choice and its consequences.
- A one-page design doc (Part 2) and a metric dictionary generated from Cube views.
- A before/after table: the Part 1 answer table, then the same questions passing from all three tools.
- The golden-question suite in CI, plus a migration with no consumer outage (parallel build, reconciliation, then deprecation).

## Sources

- Kimball Group, [Additive, semi-additive, and non-additive facts](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/additive-semi-additive-non-additive-fact/)
- dbt Labs, [Semantic Layer best practices: conclusion](https://docs.getdbt.com/best-practices/how-we-build-our-metrics/semantic-layer-9-conclusion), [Refactor a rollup](https://docs.getdbt.com/best-practices/how-we-build-our-metrics/semantic-layer-8-refactor-a-rollup), [Building semantic models](https://docs.getdbt.com/best-practices/how-we-build-our-metrics/semantic-layer-3-build-semantic-models), [Advanced metrics](https://docs.getdbt.com/best-practices/how-we-build-our-metrics/semantic-layer-5-advanced-metrics)
- dbt Labs, [Semantic Layer vs. Text-to-SQL: 2026 benchmark](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
- dbt Labs, [Announcing open source MetricFlow](https://www.getdbt.com/blog/open-source-metricflow-governed-metrics) (14 Oct 2025); [OSI commitment](https://www.getdbt.com/blog/dbt-labs-affirms-commitment-to-open-semantic-interchange-by-open-sourcing-metricflow)
- Cube, [dbt recipe](https://docs.cube.dev/recipes/data-modeling/dbt), [Style guide](https://docs.cube.dev/recipes/data-modeling/style-guide), [Views](https://docs.cube.dev/docs/data-modeling/views), [AI context](https://docs.cube.dev/docs/data-modeling/ai-context), [Designing metrics](https://docs.cube.dev/recipes/data-modeling/designing-metrics), [Multi-stage calculations](https://docs.cube.dev/docs/data-modeling/concepts/multi-stage-calculations)
- Lightdash, [Modeling strategies](https://docs.lightdash.com/semantic-layer/modeling-strategies)
- Secondary, vendor or disputed: [AtScale benchmark](https://www.atscale.com/blog/semantic-layer-text-to-sql-accuracy/), [Atlan: dbt Semantic Layer vs Cube](https://atlan.com/know/ai-agent/semantic-layer/dbt-semantic-layer-vs-cube/), [Datus: converting semantic models to Ossie](https://datus.ai/blog/convert-semantic-models-to-ossie/)
