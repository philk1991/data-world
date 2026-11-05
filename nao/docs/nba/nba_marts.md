# NBA marts — custom context

Hand-authored context for nao, distilled from `dbt/models/marts/nba/marts_nba.yml`
and the `cube/model/cubes/nba_*.yml` cubes. This complements the column-level
schema that `nao sync` pulls automatically; keep it in sync with the dbt docs if
the marts change.

All tables live in the `marts` schema of the DuckLake `lake` (query them as
`marts.<table>` — the session runs `USE lake`). Percentages/ratings
are 0–1 fractions unless noted.

## nba_game_results
**Grain:** one row per `game_id`.
One row per NBA game combining metadata and result with both teams' traditional
box score lines, pivoted onto a home/away axis. Box score columns are `NULL` for
older games where team statistics were not recorded. `point_margin` = home minus
away; `home_team_won` is boolean. Includes `attendance` and `arena_name` (often
NULL for older games).

## nba_player_career_stats
**Grain:** one row per `person_id`.
Career traditional totals, per-game averages and shooting efficiency across the
player's competitive games (Regular Season, Playoffs, Play-in Tournament, NBA Cup
Final; preseason and All-Star games excluded), enriched with bio (`is_guard/forward/center`,
`draft_year`, `height_inches`). Only games actually played (minutes recorded)
count. `first_game_date` / `last_game_date` bound the player's coverage.
Career figures cover only games present in the dataset.

## nba_player_advanced_career
**Grain:** one row per `person_id`, every era.
Career efficiency over competitive games (Regular Season, Playoffs, Play-in
Tournament, NBA Cup Final combined). Box-score rates recomputed from career
totals: `usage_pct` (from 1977-78), `true_shooting_pct`,
`effective_field_goal_pct`, `assist_pct` and `rebound_pct` (from 1964-65),
`individual_offensive_rating` / `individual_defensive_rating` (Dean Oliver's,
as on Basketball-Reference). The NBA's on-court `offensive_rating`,
`defensive_rating`, `net_rating` and `player_impact_estimate` plus
`double_doubles` / `triple_doubles` exist only from 1996-97
(`games_with_advanced`), so they are null for older careers.

## nba_player_season_advanced
**Grain:** one row per (`person_id`, `season_start_year`, `game_type`).
Box-score advanced metrics for a player's season, all rates 0-1: `true_shooting_pct`,
`effective_field_goal_pct`, `three_point_attempt_rate`, `free_throw_rate`,
`true_shooting_points_added`, `usage_pct`, `turnover_pct`, `assist_pct`,
`offensive_rebound_pct`, `defensive_rebound_pct`, `rebound_pct`, `steal_pct`,
`block_pct`; per-100 production (`points_per_100`, `rebounds_total_per_100`,
`assists_per_100`, `steals_per_100`, `blocks_per_100`, `turnovers_per_100`);
`game_score_per_game`; and `individual_offensive_rating` /
`individual_defensive_rating`. A traded player's teams are combined into one row
(`is_multi_team`, `team_count`, `primary_team_id`). **Filter `game_type =
'Regular Season'` and set a `total_minutes` minimum** (500 for a full season)
before ranking rates. Coverage: usage, turnover % and offensive rating from
1977-78; steal/block/offensive-rebound %, per-100 and defensive rating from
1973-74; assist and rebound % from 1964-65. Individual defensive rating mostly
reflects the team's defence.

## nba_player_stint_advanced
**Grain:** one row per (`person_id`, `team_id`, `season_start_year`,
`game_type`). The same metrics as `nba_player_season_advanced`, split by team
for players traded mid-season. Use it for "how did X play for team Y".

## nba_player_season_stats
**Grain:** one row per (`person_id`, `season_start_year`, `game_type`).
Season-level traditional totals, per-game averages and shooting splits, enriched
with bio. Season comes from the game id (so the 2020 bubble games belong to
2019-20). A mid-season-traded player is combined into one row per
game type, with `primary_team_id` = the team they played the most games for.
Split by `game_type` so you can compare regular-season vs playoff production —
**filter `game_type = 'Regular Season'` for league-leader questions.** This is the
season-grain counterpart to `nba_player_career_stats`.

## nba_player_game_stats
**Grain:** one row per (`person_id`, `game_id`), games played only (minutes
recorded). The box score for each game with its context (date, season, game
type, team, opponent, home/away, result, starter), `is_double_double` /
`is_triple_double`, and advanced efficiency (usage, TS%, ratings, PIE) from
1996-97 on. Its rows add up exactly to `nba_player_season_stats`, so use it for
game logs, single-game highs, streaks and recent form, and the season mart for
season totals.

## nba_player_shot_zones
**Grain:** one row per (`person_id`, `season_start_year`, `game_type`,
`shot_zone`), from the play-by-play (1996-97 on). Zones are the NBA's court
areas computed from shot coordinates: Restricted Area (under 4 ft), In The
Paint (Non-RA), Mid-Range (other twos), Corner 3, Above the Break 3, and Heave
(40+ ft). Per zone: attempts, makes, field goal %, points per shot, the share
of the player's attempts, and the league's field goal %, points per shot and
share of attempts for the same zone and season. Field goals only.
`points_per_shot` is the fairest way to compare zones, since threes are worth
more. Rates are noisy on few attempts: filter on `field_goals_attempted`.

## nba_player_clutch_stats
**Grain:** one row per (`person_id`, `season_start_year`, `game_type`) with any
clutch event, from the play-by-play (1996-97 on). Clutch time is the last five
minutes of the fourth quarter or overtime with the score within five points.
Clutch points, shooting splits, true shooting (with the player's all-minutes
true shooting for the season as a baseline), rebounds, turnovers and go-ahead
field goals. `clutch_games` counts games with a clutch event of the player's
own, not every game they were on the floor in the clutch. No assists, steals
or blocks (the pre-2019-20 play-by-play lacks them).

## nba_team_season_summary
**Grain:** one row per (`team_id`, `season_start_year`).
Regular-season record: `wins`, `losses`, `home_wins`, `away_wins`, `win_pct`, and
scoring (`points_for_per_game`, `points_against_per_game`,
`point_margin_per_game`). Restricted to Regular Season games. `season_label` is
the readable season (e.g. "2023-24"). Best-record / standings questions live here.

## nba_team_advanced_profile
**Grain:** one row per (`team_id`, `season_start_year`, `game_type`) — game_type
is Regular Season, Play-in Tournament, Playoffs or NBA Cup Final, so **filter
`game_type = 'Regular Season'`** for normal season questions.
Season efficiency computed from summed season counts: `offensive_rating`,
`defensive_rating`, `net_rating`, `pace`, `possessions`; the Four Factors on
offence (`effective_field_goal_pct`, `turnover_pct`, `offensive_rebound_pct`,
`free_throw_rate`) and defence (`opp_effective_field_goal_pct`,
`opp_turnover_pct`, `defensive_rebound_pct`, `opp_free_throw_rate`);
`true_shooting_pct`, `assist_pct`, `rebound_pct`; shot profile
(`three_point_attempt_rate`, `points_in_paint_share`, `fast_break_points_share`);
record quality (`wins`, `losses`, `margin_of_victory`, `pythagorean_wins`,
`luck_wins`); schedule-adjusted strength (`simple_rating_system`,
`strength_of_schedule`, Regular Season only); and gaps to the league average
(`relative_offensive_rating`, `relative_defensive_rating`, `relative_pace`,
`relative_effective_field_goal_pct`, `relative_true_shooting_pct`).
Covers every season from 1946-47, but ratings, pace and turnover/rebound shares
start in 1973-74 (complete from 1983-84) and the three-point rate in 1979-80;
`coverage_flag` ('full', 'partial', 'shooting_only', 'scores_only') says how
complete a season is. Pair with `nba_team_season_summary` to explain *how* a
team achieved its record. "Best team by SRS" / "luckiest team" live here.

## nba_team_game_stats
**Grain:** one row per (`game_id`, `team_id`), competitive games only.
Both teams' box counts (opponent columns prefixed `opp_`), `possessions`,
`pace`, `offensive_rating`, `defensive_rating`, `net_rating`, the eight Four
Factors and style rates for a single game. Ratings from 1973-74. For a period,
sum the counts and recompute — never average these rows' rates.

## nba_league_season_baselines
**Grain:** one row per (`season_start_year`, `game_type`).
League totals (`lg_points`, `lg_field_goals_attempted`, ...) and league averages
(`lg_pace`, `lg_offensive_rating`, `lg_points_per_possession`,
`lg_true_shooting_pct`, `lg_effective_field_goal_pct`,
`lg_three_point_attempt_rate`, `lg_free_throw_rate`, `lg_turnover_pct`,
`lg_offensive_rebound_pct`, `lg_points_per_game`). Use for league-wide trends
("how has pace changed since 1980").

## nba_team_form
**Grain:** one row per (`game_id`, `team_id`), 1973-74 on.
A team's form going into a game, from earlier games only:
`last_10_net_rating`, `last_20_net_rating`, `season_to_date_net_rating` (with
`*_games` sample sizes) and the league's `league_to_date_offensive_rating` and
`league_to_date_pace`. For "current form", take each team's latest `game_date`.

## nba_team_dim
**Grain:** one row per `team_id`.
The conformed franchise dimension: current identity (`current_team_city`,
`current_team_name`, `current_full_name`, `current_team_abbrev`,
`current_league`) with relocation/rename history rolled up
(`franchise_first_season`, `franchise_era_count`, `has_relocated_or_renamed`).
Use this to turn any `team_id` into a readable name.

## nba_team_head_to_head
**Grain:** one row per (`team_id`, `opponent_team_id`).
All-time matchup record from `team_id`'s perspective (the reverse matchup is a
separate row). Restricted to competitive meetings (Regular Season, Playoffs,
Play-in Tournament, NBA Cup Final); preseason and All-Star games are excluded.
`wins`/`losses`/`win_pct`, average points for/against/margin, and
`first_meeting_date` / `last_meeting_date`. Join to `nba_team_dim` on either id
for readable names.
