# NBA marts — custom context

Hand-authored context for nao, distilled from `dbt/models/marts/nba/marts_nba.yml`
and the `cube/model/cubes/nba_*.yml` cubes. This complements the column-level
schema that `nao sync` pulls automatically; keep it in sync with the dbt docs if
the marts change.

All tables live in the `marts` schema of `spotify.duckdb`. Percentages/ratings
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
Career traditional totals, per-game averages and shooting efficiency across every
game the player appeared in, enriched with bio (`is_guard/forward/center`,
`draft_year`, `height_inches`). Only games actually played (minutes recorded)
count. `first_game_date` / `last_game_date` bound the player's coverage.
Career figures cover only games present in the dataset.

## nba_player_advanced_career
**Grain:** one row per `person_id`.
Minutes-weighted advanced career efficiency (`usage_pct`, `true_shooting_pct`,
`offensive/defensive/net_rating`, `assist_pct`, `rebound_pct`,
`player_impact_estimate`) plus `double_doubles` / `triple_doubles`. Sourced from
the advanced box scores (~1996 onward), so earlier careers are absent. Rate
metrics weight high-minute games more than cameos.

## nba_player_season_stats
**Grain:** one row per (`person_id`, `season_start_year`, `game_type`).
Season-level traditional totals, per-game averages and shooting splits, enriched
with bio. Season is derived from the game date (Oct–Apr; games before July belong
to the prior start year). A mid-season-traded player is combined into one row per
game type, with `primary_team_id` = the team they played the most games for.
Split by `game_type` so you can compare regular-season vs playoff production —
**filter `game_type = 'Regular Season'` for league-leader questions.** This is the
season-grain counterpart to `nba_player_career_stats`.

## nba_team_season_summary
**Grain:** one row per (`team_id`, `season_start_year`).
Regular-season record: `wins`, `losses`, `home_wins`, `away_wins`, `win_pct`, and
scoring (`points_for_per_game`, `points_against_per_game`,
`point_margin_per_game`). Restricted to Regular Season games. `season_label` is
the readable season (e.g. "2023-24"). Best-record / standings questions live here.

## nba_team_advanced_profile
**Grain:** one row per (`team_id`, `season_start_year`).
Season advanced efficiency: `offensive_rating`, `defensive_rating`, `net_rating`,
`pace`, four-factor (`effective_field_goal_pct`, `true_shooting_pct`,
`assist_pct`, `rebound_pct`, `turnover_pct`) and shot profile
(`three_point_attempt_rate`, `points_in_paint_share`, `fast_break_points_share`).
Coverage starts ~1996. Same grain as `nba_team_season_summary` — pair them to
explain *how* a team achieved its record.

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
separate row). Restricted to competitive meetings (Regular Season + Playoffs).
`wins`/`losses`/`win_pct`, average points for/against/margin, and
`first_meeting_date` / `last_meeting_date`. Join to `nba_team_dim` on either id
for readable names.
