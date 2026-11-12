# NBA advanced metrics — decision log

This log records decisions for the build brief in `plans/Claude Code brief NBA advanced metrics build.md`, as section 2 requires. Phase 1 (brief steps 1–5) was built in dbt on branch `nba-players-dim`, started 2026-11-05.

Scope agreed with the user:

- **Phase 1 is dbt SQL only.** It covers the audit, foundations, league baselines, team metrics and SRS.
- **Deferred:** Elo, Adjusted Net Rating and the Four Factors regression; these come back later.
- **Existing advanced marts are rebuilt in place** rather than versioned. nao is their only consumer.

## Datasets

| Dataset | Grain | Key | Coverage | Refresh | Consumers | Action |
|---|---|---|---|---|---|---|
| `stg_nba_team_statistics` | team-game | game_id, team_id | 1946-47 → today (latest game 2026-10-31) | Kaggle full-replace, `nba_pipeline` | everything team-level | reuse |
| `stg_nba_player_statistics` | player-game | game_id, person_id | 1946-47 → today | same | player marts | reuse |
| `stg_nba_*_extended` | team-game / player-game | as above | 1996-97 → | same | `nba_player_advanced_career`, `nba_player_game_stats` | reuse, for cross-checks only |
| `int_nba_player_games` | player-game, competitive types | game_id, person_id | 1946-47 → | dbt (`nba_dbt`) | `int_nba_team_games`; phase 2 player metrics | **create** |
| `int_nba_team_games` | team-game, competitive types | game_id, team_id | 1946-47 → | dbt | all team metrics | **create** |
| `int_nba_team_season_srs` | team × regular season | season_start_year, team_id | 1946-47 → | dbt | `nba_team_advanced_profile` | **create** |
| `nba_team_game_stats` | team-game | game_id, team_id | 1946-47 → (ratings from 1973-74) | dbt | new | **create** |
| `nba_league_season_baselines` | season × game_type | season_start_year, game_type | 1946-47 → | dbt | profile; phases 2–4 | **create** |
| `nba_team_advanced_profile` | team × season × game_type (was team × regular season) | team_id, season_start_year, game_type | 1946-47 → (was 1996-97 →) | dbt | nao | **modify (rebuilt in place)** |
| `nba_team_form` | team-game, as of tip-off | game_id, team_id | 1973-74 → | dbt | new | **create** |
| `nba_player_advanced_career` | player | person_id | all eras (was 1996-97 →) | dbt | nao | **modify (rebuilt in place, phase 2)** |
| `int_nba_player_game_context` | player-game | game_id, person_id | 1946-47 → | dbt | stints | **create (phase 2)** |
| `int_nba_player_stints` | player × team × season × type | person_id, team_id, season_start_year, game_type | 1946-47 → | dbt | player marts | **create (phase 2)** |
| `nba_player_stint_advanced` | player × team × season × type | as above | 1946-47 → | dbt | new | **create (phase 2)** |
| `nba_player_season_advanced` | player × season × type | person_id, season_start_year, game_type | 1946-47 → | dbt | new | **create (phase 2)** |
| `nba_game_results`, `nba_team_season_summary`, `nba_player_season_stats`, … | — | — | — | — | Cube, nao | unchanged |

## Source checks (brief section 3)

1. **Season mapping: pass.** `nba_season_start_year()` and `nba_game_type()` decode the season and type from the game id (`dbt/macros/nba_game_id.sql`). The 2020 bubble counts in 2019-20, and the July 2021 Finals in 2020-21.
2. **Game types: pass.** Ids give Preseason, Regular Season, All-Star Game, Playoffs, Play-in Tournament and NBA Cup Final. Cup group and knockout games are type 2 and count as regular season; only the Final (type 6) doesn't. The raw `gameType` column is unreliable and isn't used.
3. **Coverage: team box scores hold scores only before 1983-84.** In the regular season, FGA, ORB, STL, TOV, 3PA and AST are about 100% null in `TeamStatistics` before 1980-81, and 36–98% null in 1980–84. Player logs cover every game from 1946-47 (FGA present in 12% of games in 1946, 76% by 1960 and 99% by 1980). Player ORB and TOV are partial from 1970 to 1984. Zero-filled stats are already turned back into nulls by `null_if_unrecorded`.
4. **Early history: no season-total data exists in the project,** so pre-1983-84 work relies on summed player logs. Summed player points equal the team score in 97.6–99.9% of team games.
   - **Correction (10 Nov 2026):** the source holds only the 30 current franchises, so every game against a defunct team is missing. 1946-47 has 18 games across 3 teams, and schedules are complete only from 1954-55. "Every game" above means every game in the source, not every game played. Careers, Cube and nao now leave out seasons before 1954-55 (`plans/adr/0003-coverage-cutoff.md`).
5. **Extended files:** the dataset's own `possessions` averages about 1.0 a game higher than the box estimate here (mean absolute gap 1.44 over 76k team games). The NBA counts possessions differently, so the two are kept as separate definitions.
6. **Tracking and hustle:** none in the Extended files. Out of scope.
7. **Freshness:** latest game is 2026-10-31, with 88 games of 2026-27 loaded.

**Other data findings:**

- **Missing team ids:** `player_team_id` is null for all of 2021-22 (36k rows) and for 2–4k rows a season since 2003. `int_nba_player_games` recovers the team from `is_home` and the game's home and away ids.
- **Player minutes:** whole numbers (truncated) from 1996, summing to about 235 a game, and recorded as 0 before about 1964-65.
- **Team minutes:** the team `minutes_played` field is reliable from 1964-65, apart from a few 2026-27 games recorded as 0.

**Play-by-play gate: not yet run (phase 4).** Known risk: the legacy feed (1996-97 to 2019-20) gives the player coming in on a substitution only as a name in the description, and has no steal or block ids.

## Assumptions and deviations

**Data sources**

- **Player-sum fallback.** A team count missing from the team box is filled with the sum of that team's player rows for the game. This happens only when the sum is complete: player points equal the team score and no player who played lacks the count. Otherwise the count stays null. `counts_source` records `team_box`, `player_sum` or `none`. Player sums leave out team rebounds and team turnovers, so possessions before 1983-84 run slightly low.
- **Team minutes** come from the team box field. Where that is 0, they are rounded from summed player minutes to 240 + 25 × OT. Summed player minutes are never used directly.
- **Three-pointers** are 0 before 1979-80 (the shot didn't exist). 3PA rate is null before then.

**Calculation choices**

- ~~**Season possessions are estimated once from season totals,** not by summing game estimates. The same applies to league possessions.~~ *Reversed 10 Nov 2026 (staff AE project, ADR 0002):* season and league possessions are now the **sum of the per-game estimates**. A season-total estimate isn't additive, so Cube (which sums components) and dbt disagreed on team ratings by up to 0.5 points a regular season (1.8 in the playoffs). Player metrics already summed per-game possessions. The cost is a small departure from Basketball-Reference's season-total convention: league ORtg moved by 0.06 points on average. The possession formula now lives only in `int_nba_team_games`.
- **Per-game averages divide by the games with the stat recorded** (12 Nov 2026, staff AE project). Box scores before the 1980s often leave a player's rebounds, assists, minutes, steals or turnovers blank: half the 1950s player-games have no assists. A blank is not a zero, so dividing the recorded total by every game played understated those eras (Bill Russell's career rebounds 22.0 a game against the official 22.5; Andy Phillip's 1954-55 assists 1.6 against 7.7). The season and career marts carry `games_with_minutes`, `games_with_rebounds`, `games_with_assists`, `games_with_steals`, `games_with_blocks` and `games_with_turnovers` as the denominators, which add up across rows, and Cube divides by the same sums. Totals stay the sum of what was recorded, so they remain partial for those eras. Found by the Cube reconciliation (`task cube:reconcile`): the player-game cube already averaged over recorded games and disagreed with 4.6% of season rows.
- **Team three-point attempt rate is null before 1979-80 in Cube too.** `nba_team_game_stats.three_par_field_goals_attempted` is the denominator from the line's first season, so a Cube sum over earlier seasons gives null, not 0.
- **Ratings, pace and possession-based shares start in 1973-74.** They use only games with a full box on both sides (`has_full_box`, which also requires team minutes). Shooting rates use games with box counts. `coverage_flag` and the `games_with_*` columns show the samples.
- **SRS is regular season only.** The iteration oscillates on playoff brackets and disconnected play-in pairs (checked: 500 iterations without converging). Basketball-Reference also publishes regular-season SRS only. It is solved in a DuckDB recursive CTE that holds each season's ratings as a list; regular seasons converge in about 11–16 iterations.
- **Game types:** Regular Season, Play-in Tournament, Playoffs and NBA Cup Final are each computed separately. Preseason and All-Star games are excluded. The Cup Final is never part of regular-season totals or baselines.
- **`nba_team_advanced_profile` changed grain** to include `game_type`, so readers must filter `game_type = 'Regular Season'` for standings seasons. All existing columns are kept. Values are now computed from summed counts rather than averaged per-game rates, so they shift slightly.

**Definitions and versioning**

- **One definition per formula** in `dbt/macros/nba_metrics.sql`. Every metric mart carries `formula_version` (the dbt var `nba_metrics_version`, currently `v1`).
- **`point_margin`** now has named doc variants: `__game` for home minus away, `__team` for team minus opponent.

## Metrics

Actions follow the brief: reuse, modify, create or blocked. `deferred` means out of phase-1 scope.

### Section 4–5: team

| Metric | Status | Action | Target | Grains | Inputs | Coverage | Reason |
|---|---|---|---|---|---|---|---|
| Possessions (box) | did not exist (NBA's own `possessions` uses a different formula) | create | `int_nba_team_games`, `nba_team_game_stats`, profile, baselines | team-game, team-season, league-season | FGA, FTA, ORB, DRB, FG, TOV, both sides | 1973-74 → | BBRef formula; kept apart from the NBA's figure |
| Pace | existed, averaged per game | modify | game stats, profile, baselines | as above | possessions, team minutes | 1973-74 → | from summed counts |
| ORtg / DRtg / NetRtg | existed, averaged per game, 1996 → | modify | game stats, profile, form | team-game, team-season, as-of | points, possessions | 1973-74 → | from summed counts; coverage widened |
| MOV | did not exist (`nba_team_season_summary.point_margin_per_game` is regular season only) | create | profile (`margin_of_victory`) | team-season × type | scores | all seasons | needed for SRS |
| eFG, TOV%, ORB%, FT rate (offence) | eFG and TOV% existed, averaged | modify / create | game stats, profile, baselines | team-game, team-season, league | box counts | eFG and FT rate all seasons with counts; TOV% and ORB% 1973-74 → | Suns fixture matches to 3 dp |
| Opp eFG, Opp TOV%, DRB%, Opp FT rate | did not exist | create | game stats, profile | team-game, team-season | opponent box counts | as above | |
| 3PA rate | existed, averaged | modify | game stats, profile, baselines | all | 3PA, FGA | 1979-80 → | |
| AST rate (`assist_pct`) | existed, averaged | modify | game stats, profile | all | AST, FG | seasons with counts | kept the existing name `assist_pct` |
| TS% | existed, averaged | modify | game stats, profile, baselines | all | PTS, FGA, FTA | seasons with counts | |
| Pythagorean wins, luck wins | did not exist | create | profile | team-season × type | scores | all seasons | exponent 14 |
| League baselines `Lg_*` | did not exist | create | `nba_league_season_baselines` | season × type | team-game counts | 1946-47 → (totals null unless complete) | |
| SRS, SOS | did not exist | create | `int_nba_team_season_srs` → profile | team × regular season | scores, schedule | all seasons | regular season only (see above) |
| Relative-to-league (ORtg, DRtg, pace, eFG, TS) | did not exist | create | profile | team-season × type | profile, baselines | as inputs | |
| Team form: last 10 / 20 / season-to-date NetRtg; league-to-date ORtg and pace | did not exist | create | `nba_team_form` | team-game as of tip-off | team-games before the game | 1973-74 → | |
| Four Factors decomposition (era regressions) | — | deferred | — | — | — | — | user: no regressions in phase 1 |
| Adjusted Net Rating (least squares) | — | deferred | — | — | — | — | as above |
| Elo, average opponent Elo | — | deferred | — | — | — | — | user: Elo later |

### Section 6: player (phase 2, built 2026-11-05)

| Metric | Status | Action | Target | Grains | Inputs | Coverage | Reason |
|---|---|---|---|---|---|---|---|
| TS%, eFG%, 3PA rate, FT rate | TS and eFG came per game from the Extended file (1996 →) and were minute-weighted in `nba_player_advanced_career` | modify / create | `nba_player_stint_advanced`, `nba_player_season_advanced`, career | stint, player-season, career | player box counts | where attempts are recorded; 3PA rate 1979-80 → | from summed counts |
| TS points added | did not exist | create | stint, season | stint, player-season | counts, league TS% | as TS | league TS is computed with the same `nba_ts` macro |
| USG%, TOV% | USG came from the Extended file only | modify (career) / create | stint, season, career | as above | player and team FGA/FTA/TOV | 1977-78 → | box estimate |
| AST%, TRB% | Extended file only | modify (career) / create | as above | as above | team FG; team and opponent TRB | 1964-65 → (needs minutes) | |
| ORB%, DRB%, STL%, BLK% | did not exist | create | stint, season | stint, player-season | team/opponent rebounds, possessions, opponent 2PA | 1973-74 → | |
| Per-100 production (PTS, TRB, AST, STL, BLK, TOV) | did not exist | create | stint, season | as above | team possessions × on-court share | 1973-74 → | |
| Game Score | did not exist | create | `nba_player_game_stats.game_score`; `game_score_per_game` on stint and season | player-game, stint, season | box counts | where every input is recorded | |
| Individual ORtg (Oliver), PProd, TotPoss | the Extended `offensive_rating` is the NBA's on-court rating | add a version | stint, season, career (`individual_offensive_rating`) | stint, player-season, career | player/team/opponent stint totals | 1977-78 → | keeps the NBA's rating under its existing name |
| Individual DRtg (Oliver) | as above | add a version | `individual_defensive_rating` | as above | as above | 1973-74 → where inputs exist (in practice mostly 1983-84 →) | labelled team-dependent |
| Player as-of rolling metrics | — | deferred (section 9 current form) | — | — | — | — | built with shrinkage and decay |

**Phase 2 assumptions and deviations**

- **Minutes format fix (staging).** From 2024-25 the source writes most player minutes as mm.ss (19.38 = 19:38); late 2025-26 and 2026-27 use true decimals. The new `nba_minutes` macro (in `stg_nba_player_statistics` and its extended twin) reads each team-game as mm.ss when every fraction is below .60 and that reading sums to 240 + 25 × OT; otherwise it reads decimals. 2024+ team-games now sum to 240 in 97–100% of cases, up from a median of 238. This changes the displayed minutes in `nba_player_game_stats` for 2024+, which were understated before.
- **Team-context rates sum per-game opportunities.** Each game adds the player's on-court share of the team's chances (share = MP / (Tm_MP / 5)). A rate over any period is SUM(numerator) / SUM(opportunity), so stints, seasons and careers aggregate the same way. On the same data this matches Basketball-Reference's season-total formula to 3 dp (checked on LeBron 2008-09 and 2016-17 for TRB%, AST% and USG%).
- **Tm_MP for player formulas** is the team's summed player minutes in each game, not 240. Player minutes before 2024-25 are truncated (about 235 a game), so using the same source on both sides keeps the floor shares summing to 5. Player MP still runs about 1% below Basketball-Reference's (LeBron 2008-09: 3017 against 3054).
- **Oliver ratings use stint totals,** meaning team and opponent totals over the games the player played for that team, and only games where every input exists (`rating_games`). Season and career values sum PProd and TotPoss across stints. DRtg is weighted by on-floor possessions.
- **Rates are on a 0–1 scale** (the project convention), not the brief's ×100.
- **Team total rebounds = ORB + DRB** wherever both resolve, from either the team box or the player sums. The 1984-85 team box has totals but no offensive/defensive split, and its totals include about 6.3 team rebounds a game that the player-summed split leaves out. This was found by the new usage/rebound balance test.
- **Impossible shooting pairs (found by profiling, fixed 2026-11-06).** A few 1959–62 team box scores record more field goals made than attempted (one game: 8 FGA), and some early player sums do too. That produced team-game eFG up to 5.1. `int_nba_team_games` now nulls any shooting pair with makes > attempts, first in the team box (so the player-sum fallback can recover it) and again after the fallback. `counts_source` becomes `none` when the field-goal pair is dropped. The same step nulls team assists in the 9 team-games (1953–83) that record more assists than made field goals.
- **Partial-roster minutes (found by profiling, fixed 2026-11-06).** Some 1951–84 games record minutes for only part of the roster, which inflated `on_court_share` to as much as 5.0. Floor shares, and every opportunity and Oliver input built on them, are now null unless the recorded player minutes cover at least 95% of the game. That excludes 4.4% of pre-1996 team-games and essentially no later ones (truncated minutes still cover about 98%). Test: `assert_nba_shooting_and_shares_are_possible`.
- **`primary_team_id`** is the team the player played the most games for, matching `nba_player_season_stats`.
- **`nba_player_advanced_career` rebuilt in place.**
  - All existing columns are kept. Box-score rates are recomputed from counts across every era.
  - The NBA on-court ratings are now weighted by on-court possessions rather than minutes. PIE stays minute-weighted.
  - Pre-1996 players now appear, with null on-court ratings.
  - New columns: `games_played`, `individual_offensive_rating`, `individual_defensive_rating` and `formula_version`.
  - `minutes_per_game` now covers every game with recorded minutes.
- **Multi-team players:** `nba_player_stint_advanced` holds one row per team. `nba_player_season_advanced` holds the combined row, flagged by `is_multi_team` and `team_count`. The brief's "total row" is a separate mart rather than an extra row, so the two grains can't be double-counted.

**Phase 2 validation**

- **Brief fixture, 2008-09 LeBron James:** PProd 2347.1 (2345.9), TotPoss 1929.5 (1928.1), individual ORtg 121.6 (121.7), DRtg 99.0 (99.1). The singular test `assert_nba_individual_ratings_match_bbref_fixture` allows ±0.3.
- **Balance:** minute-weighted league usage is 0.200 and total rebound share 0.100 in every regular season from 1983-84 (test `assert_nba_player_shares_balance`).
- **TS points added** sums to about 0 across the league in complete seasons.
- **No direct reference comparison yet.** Basketball-Reference refuses automated fetches (HTTP 403), so beyond the fixture there is no reference comparison of USG%, AST% and the other rates. That still needs reference data in the project.

### Section 7: all-in-one (phase 3)

BPM 2.0, OBPM, DBPM, VORP, Win Shares (all eras) and PER are **deferred to phase 3**. BPM and Win Shares need season-level team context and the league baselines, which now exist. There is no Basketball-Reference season data to calibrate against, so BPM would be labelled `bpm_2_0_approx` unless calibration data is added.

### Section 8: play-by-play (phase 4)

On/off, lineups, `pbp_poss`, `average_lead`, the garbage-time filter and RAPM are **deferred: the gate is not yet run.** The legacy-feed substitution names are the main risk.

### Section 9: era comparison and current form (phase 3)

Z-scores, percentiles, indexes, shrunk rates and decay-weighted rates are **deferred.** Team relative-to-league columns are delivered now.

## Validation (phase 1)

**Fixtures and reference values** (Basketball-Reference figures in brackets):

- **2004-05 Suns Four Factors:** all eight match to 3 dp (unit test `nba_team_game_stats_four_factors_match_bbref_fixture`).
- **2004-05 Suns season totals rebuilt from the pipeline:** FG 3351, FGA 7018, TOV 1125, FTA 2080 and ORB 967, matching the fixture exactly.
- **2004-05 Suns season:** ORtg 114.5 (114.5), DRtg 107.1 (107.1), pace 95.9 (95.9), SRS 7.08 (7.08).
- **2015-16 Warriors:** ORtg 114.5 (114.5), DRtg 103.8 (103.8), pace 99.3 (99.3), SRS 10.38 (10.38).
- **1985-86 Celtics:** SRS 9.06 (9.06); ORtg 112.2 / DRtg 103.0, about +0.4 above Basketball-Reference's figures.
- **1985-86 Lakers:** SRS 6.84 (6.84).

**Data tests:**

- Two rows per game, and points equal the opponent's opponent points.
- Team minutes equal 240 + 25 × OT (≤ 0.1% off).
- Player points sum to the team score (≥ 97% before 1983-84, ≥ 99% after).
- League net rating and SRS centre on 0 (|mean| < 0.05).
- Pythagorean RMSE is below 4 wins (1983-84 to the last finished season).
- No possession metric before 1973-74 and no 3PA rate before 1979-80.
- Rates stay within 0–1, and pace within 60–140.
- As-of form never uses the current or later games.
- Unique grain keys on every model.

**Not yet covered:**

- A multi-season reference comparison (1975, 1985, 1998, 2012 and the latest season) with mean absolute error by metric. Only spot checks have been done.
- The latest-game-date alert and the closed-season row-count drift check.
