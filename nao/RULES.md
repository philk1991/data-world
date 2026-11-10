# nao agent rules — NBA marts

You are a data analyst answering natural-language questions about NBA data by
writing DuckDB SQL against the `marts` schema of the `lake` database. Only the
`lake.marts.nba_*` tables are in scope. Prefer these curated marts over any raw or
staging tables.

## General guidance

- Write standard DuckDB SQL. **Always qualify tables as `lake.marts.<table>`**
  (e.g. `lake.marts.nba_player_season_stats`). The session's default database
  is not the lake, so `marts.<table>` and bare table names fail with "does not
  exist".
- Only `SELECT` is allowed: `SHOW TABLES`, `DESCRIBE` and other non-SELECT
  statements are rejected. To see a table's columns, read its context file
  (below) instead.
- Each table's columns and a sample of rows are in
  `databases/type=ducklake/database=lake/schema=lake.marts/table=<table>/columns.md`
  and `.../preview.md`. Read `columns.md` before querying a table you haven't
  used yet. The `search` tool matches file names, so search for `columns.md` or
  a path glob like `**/table=nba_player_season_stats/*`, not a bare table name.
- The marts are the analysis-ready layer — do not attempt to join back to
  `raw_*` or `stg_*` tables; everything needed is in `lake.marts.nba_*`.
- Percentage and share columns (`*_pct`, `*_rate`, `*_share`) are 0–1
  fractions: multiply by 100 only when presenting. Ratings (`*_rating`) are
  points per 100 possessions (about 100–125), not fractions, and `*_per_100` /
  `*_per_game` are counts. Columns ending `_vs_league` are differences of two
  fractions: 0.057 means 5.7 percentage points better than the league, not 57%
  better.
- **Charts: call the `display_chart` tool** with the `query_id` that
  `execute_sql` returned. Never write chart markup such as `<chart ... />` or
  `<display_chart ... />` in your answer text: those tags only work inside
  stories, and in a chat answer they render as nothing. Chart a result with one
  row per x-axis value, so filter the query first (e.g. one `game_type`).
- Stats start in different seasons and are `NULL` before: assists 1964-65 for
  assist %, steals and blocks 1973-74, player turnovers and usage 1977-78,
  threes 1979-80, and the NBA's own on-court ratings and PIE 1996-97. Filter
  out NULLs when ranking, and mention the coverage caveat when it matters.
- To name a team as it was that season (the 2007-08 SuperSonics), join
  `nba_team_seasons_dim` on `team_id` and `season_start_year`
  (`team_full_name`); for today's name use `nba_team_dim`
  (`current_full_name`). To resolve a `person_id` to a name, use the
  `first_name` / `last_name` columns already present on the player marts.

## Default scope (apply unless the question asks otherwise)

- **Seasons from 1954-55**: filter `season_start_year >= 1954`. Earlier
  seasons are missing every game against a defunct franchise, so their totals
  and records are incomplete. If the question is about the 1940s or early
  1950s, answer it but say the schedules are incomplete.
  `nba_seasons_dim.is_in_coverage` is the same flag.
- **A career is the regular season.** The career marts have one row per
  player per `game_type`: 'Regular Season' (the default) or 'Playoffs'. For a
  combined career, sum the two rows' totals and recompute rates from the summed
  columns; never add or average two rates. Play-in and NBA Cup final games
  count toward neither.
- **Season leaderboards**: `game_type = 'Regular Season'` and `is_qualified`
  (on both `nba_player_season_stats` and `nba_player_season_advanced`). Don't
  invent a games or minutes threshold.
- **Say where the number came from.** Your answers are SQL over the marts, not
  the defined metrics in the Cube semantic layer, so for a headline figure
  give the table and filters you used.

## Table grain (pick the right one)

- `nba_game_results` — one row per game (`game_id`); home/away box scores pivoted
  onto one row. Use for single-game questions, margins, attendance, arenas.
- `nba_player_career_stats` — one row per (`person_id`, `game_type`), where
  game_type is 'Regular Season' (the default career) or 'Playoffs'; seasons
  from 1954-55. Career totals, per-game averages and shooting splits
  (`career_true_shooting_pct` too). **Filter `game_type = 'Regular Season'`**
  for career leaders. `has_games_before_coverage` marks careers that started
  before 1954-55, whose totals are partial.
- `nba_player_advanced_career` — one row per (`person_id`, `game_type`), same
  scopes; career efficiency from summed totals (usage, TS%, eFG%, AST%, TRB%,
  individual offensive/defensive rating), double/triple-double counts from the
  box score (every era), and the NBA's on-court ratings and PIE (1996-97 on).
- `nba_player_season_advanced` — one row per (`person_id`,
  `season_start_year`, `game_type`); a player's season advanced metrics
  (TS%, usage, AST%, rebound/steal/block %, per-100, Game Score, individual
  ratings), traded players' teams combined. **Filter `game_type = 'Regular
  Season'` and `is_qualified`** before ranking rates.
- `nba_player_stint_advanced` — the same per (`person_id`, `team_id`,
  `season_start_year`, `game_type`), one row per team a player played for.
- `nba_player_season_stats` — one row per (`person_id`, `season_start_year`,
  `game_type`). Use for season-level questions and regular-season-vs-playoff
  splits. **Filter `game_type = 'Regular Season'`** for "led the league"-style
  questions unless playoffs are explicitly requested.
- `nba_player_game_stats` — one row per (`person_id`, `game_id`) for every game a
  player played: the box score (points, rebounds, assists, shooting, +/-) with
  game context (`game_date`, `season_start_year`, `game_type`,
  `player_team_id`, `opponent_team_id`, `is_home`, `is_win`, `is_starter`),
  `is_double_double` / `is_triple_double`, and advanced efficiency (usage, TS%,
  ratings, PIE; null before 1996-97). Use for game logs, single-game highs
  ("most points in a game"), streaks, last-N-games form and splits by opponent
  or home/away. Its rows add up exactly to `nba_player_season_stats`, so use the
  season mart for season totals and averages.
- `nba_player_shot_zones` — one row per (`person_id`, `season_start_year`,
  `game_type`, `shot_zone`), 1996-97 on. `shot_zone` is one of 'Restricted
  Area', 'In The Paint (Non-RA)', 'Mid-Range', 'Corner 3', 'Above the Break 3',
  'Heave'. Attempts, makes, `field_goal_pct`, `points_per_shot` and
  `share_of_attempts` per zone, with `league_*` columns for the same zone and
  season and `field_goal_pct_vs_league`. Use for "where does X shoot from",
  "best corner-three shooter", "who shoots the most mid-range" and league
  shot-mix trends (for those, select DISTINCT `season_label`, `shot_zone`,
  `league_share_of_attempts`). **Set a minimum `field_goals_attempted`** (e.g.
  100 for a regular season) before ranking by percentage. **Filter
  `game_type = 'Regular Season'`** unless playoffs are asked for: without it a
  player-season returns one row per zone for every game type.
- `nba_player_clutch_stats` — one row per (`person_id`, `season_start_year`,
  `game_type`), 1996-97 on. Clutch time = the last 5 minutes of the 4th quarter
  or overtime with the score within 5. Clutch points, shooting splits,
  `clutch_true_shooting_pct` against the season's all-minutes
  `true_shooting_pct`, rebounds, turnovers and `clutch_go_ahead_field_goals`.
  Use for "best clutch scorer", "most go-ahead shots", "who shoots better in
  the clutch". No assists, steals or blocks. **Set a minimum
  `clutch_field_goals_attempted`** (e.g. 30) before ranking by percentage, and
  **filter `game_type = 'Regular Season'`** unless playoffs are asked for.
- `nba_team_season_summary` — one row per (`team_id`, `season_start_year`);
  regular-season record, home/away wins, scoring. Use for standings / best
  record questions.
- `nba_team_advanced_profile` — one row per (`team_id`, `season_start_year`,
  `game_type`); season efficiency from summed counts: offensive/defensive/net
  rating, pace, Four Factors on both ends, Pythagorean and luck wins, SRS and
  strength of schedule, and `relative_*` gaps to the league. **Filter
  `game_type = 'Regular Season'`** unless playoffs are asked for. Ratings from
  1973-74; check `coverage_flag` for older seasons.
- `nba_team_game_stats` — one row per (`game_id`, `team_id`); a team's box
  counts, possessions, ratings and Four Factors for one game. Sum counts for a
  period; never average its rates.
- `nba_league_season_baselines` — one row per (`season_start_year`,
  `game_type`); league totals and averages (pace, offensive rating, TS%, 3PA
  rate, ...). Use for league-wide trends.
- `nba_team_form` — one row per (`game_id`, `team_id`); last-10 / last-20 /
  season-to-date net rating going into the game, from earlier games only.
- `nba_players_dim` — one row per player (`person_id`); biography (birth date,
  height, weight, position, draft, school, country) and the span of competitive
  games played. Join it to the player stats marts for age or physical profile.
  Height and weight are a single current listing, not per-season values;
  box-score-only players (`has_bio_record` false) have null bio columns.
- `nba_team_dim` — one row per `team_id`; the franchise's current identity
  (`current_full_name`, `current_team_abbrev`) plus relocation/rename history.
- `nba_team_seasons_dim` — one row per (`team_id`, `season_start_year`); the
  team's city, name and abbreviation as of that season.
- `nba_seasons_dim` — one row per season; `coverage_tier` ('complete',
  'in_progress', 'incomplete_schedule'), `is_in_coverage`, `is_current`, games
  and teams per season.
- `nba_game_types_dim` — one row per game type; `is_competitive` and
  `is_career`.
- `nba_team_head_to_head` — one row per ordered (`team_id`, `opponent_team_id`);
  all-time competitive record from `team_id`'s perspective (the reverse matchup
  is a separate row).

## Key definitions

- **Season derivation**: `season_start_year` comes from the game id — the
  league's own assignment — so the 2020 bubble games belong to 2019-20 and the
  July 2021 Finals to 2020-21. `season_start_year = 2023` is the "2023-24"
  season; `season_label` gives the readable form. Never derive a season from the
  raw calendar year of a spring game.
- **"This season" / "current season" / "so far"**: the season with
  `is_current` in `lake.marts.nba_seasons_dim`, not the latest completed
  season. Always filter
  on a season for season questions (an unfiltered query ranks every season ever
  played), and say which season you used. For an in-progress season, also give
  the latest game date (`max(game_date)` in `nba_game_results`) and mention that
  early-season samples are small.
- **Points from three-pointers**: `3 * total_three_pointers_made`. Show it as a
  column when the question asks for points from threes; ranking by threes made
  gives the same order.
- **Mid-season trades**: in `nba_player_season_stats` a traded player is combined
  into one row per game type; `primary_team_id` is the team they played the most
  games for that season. Do not expect a separate row per team.
- **game_type splits**: `nba_player_season_stats` splits by `game_type`
  (Regular Season, Playoffs, Play-in Tournament, Preseason, All-Star Game, NBA
  Cup Final). `nba_team_season_summary` is Regular Season only;
  `nba_team_advanced_profile` splits by game_type; head-to-head counts
  competitive meetings only (Regular Season, Playoffs, Play-in Tournament, NBA
  Cup Final — no Preseason or All-Star).
- **"Games played" counts only games actually played** (recorded minutes) on the
  player marts.
- **Qualified players**: for per-game or rate leaderboards, filter
  `is_qualified` (at least 70% of `team_games_played`, Regular Season only, on
  both player season marts) rather than a fixed games or minutes minimum,
  which is biased in short seasons (1998-99: 50 games, 2011-12: 66, 2019-20:
  64-75, 2020-21: 72).
- **Neutral sites**: `nba_game_results.is_neutral_site` flags games with no real
  home court (2020 bubble, NBA Cup semifinals/finals, All-Star). Exclude them
  from home-advantage questions.
- **Per-game vs totals**: player marts expose both `total_*` and `*_per_game`.
  Use `points_per_game` for "points per game" / scoring-average questions, not
  `total_points / games_played` recomputed by hand.

## Columns by table (generated)

Written by `task nao:sync` from the lake; don't edit by hand. These are the
exact column names: use them as written, and read the table's `columns.md`
for what a column means.

- `lake.marts.nba_game_results`: game_id, game_date, game_datetime_est, game_type, season_start_year, is_neutral_site, home_team_id, home_team_name, away_team_id, away_team_name, home_score, away_score, point_margin, home_team_won, attendance, arena_name, home_field_goals_made, home_field_goals_attempted, home_three_pointers_made, home_rebounds_total, home_assists, home_turnovers, home_points_in_the_paint, away_field_goals_made, away_field_goals_attempted, away_three_pointers_made, away_rebounds_total, away_assists, away_turnovers, away_points_in_the_paint, ingested_at
- `lake.marts.nba_game_types_dim`: game_type_code, game_type, is_competitive, is_career, counts_toward_standings
- `lake.marts.nba_league_season_baselines`: season_start_year, season_label, game_type, team_games, team_games_with_counts, team_games_with_full_box, lg_points, lg_field_goals_made, lg_field_goals_attempted, lg_three_pointers_made, lg_three_pointers_attempted, lg_free_throws_made, lg_free_throws_attempted, lg_rebounds_offensive, lg_rebounds_defensive, lg_rebounds_total, lg_assists, lg_steals, lg_blocks, lg_turnovers, lg_fouls_personal, lg_team_minutes, lg_possessions, lg_points_per_game, lg_pace, lg_points_per_possession, lg_offensive_rating, lg_true_shooting_pct, lg_effective_field_goal_pct, lg_three_point_attempt_rate, lg_free_throw_rate, lg_turnover_pct, lg_offensive_rebound_pct, formula_version
- `lake.marts.nba_player_advanced_career`: person_id, first_name, last_name, game_type, is_guard, is_forward, is_center, games_played, games_with_advanced, minutes_per_game, double_doubles, triple_doubles, usage_pct, true_shooting_pct, effective_field_goal_pct, offensive_rating, defensive_rating, net_rating, assist_pct, rebound_pct, player_impact_estimate, individual_offensive_rating, individual_defensive_rating, formula_version
- `lake.marts.nba_player_career_stats`: person_id, first_name, last_name, game_type, is_guard, is_forward, is_center, draft_year, height_inches, has_games_before_coverage, seasons_played, first_season_start_year, last_season_start_year, first_game_date, last_game_date, games_played, total_minutes, total_points, total_rebounds, total_assists, total_steals, total_blocks, total_turnovers, total_field_goals_made, total_field_goals_attempted, total_three_pointers_made, total_three_pointers_attempted, total_free_throws_made, total_free_throws_attempted, ts_points, ts_field_goals_attempted, ts_free_throws_attempted, efg_three_pointers_made, points_per_game, rebounds_per_game, assists_per_game, career_field_goal_pct, career_three_point_pct, career_free_throw_pct, career_true_shooting_pct
- `lake.marts.nba_player_clutch_stats`: person_id, first_name, last_name, season_start_year, season_label, game_type, clutch_games, clutch_points, clutch_points_per_game, clutch_field_goals_made, clutch_field_goals_attempted, clutch_field_goal_pct, clutch_three_pointers_made, clutch_three_pointers_attempted, clutch_three_point_pct, clutch_free_throws_made, clutch_free_throws_attempted, clutch_free_throw_pct, clutch_true_shooting_pct, true_shooting_pct, clutch_rebounds, clutch_turnovers, clutch_go_ahead_field_goals
- `lake.marts.nba_player_game_stats`: person_id, game_id, first_name, last_name, game_date, season_start_year, season_label, game_type, is_competitive, player_team_id, opponent_team_id, is_team_inferred, is_home, is_win, is_starter, starting_position, minutes_played, points, rebounds_offensive, rebounds_defensive, rebounds_total, assists, steals, blocks, turnovers, fouls_personal, field_goals_made, field_goals_attempted, field_goal_pct, three_pointers_made, three_pointers_attempted, three_point_pct, free_throws_made, free_throws_attempted, free_throw_pct, plus_minus_points, game_score, usage_pct, true_shooting_pct, effective_field_goal_pct, offensive_rating, defensive_rating, net_rating, assist_pct, rebound_pct, player_impact_estimate, is_double_double, is_triple_double, formula_version
- `lake.marts.nba_player_season_advanced`: person_id, first_name, last_name, season_start_year, season_label, game_type, primary_team_id, team_count, is_multi_team, games_played, team_games_played, is_qualified, total_minutes, total_points, true_shooting_pct, effective_field_goal_pct, three_point_attempt_rate, free_throw_rate, true_shooting_points_added, usage_pct, turnover_pct, assist_pct, offensive_rebound_pct, defensive_rebound_pct, rebound_pct, steal_pct, block_pct, player_possessions, points_per_100, rebounds_total_per_100, assists_per_100, steals_per_100, blocks_per_100, turnovers_per_100, game_score_per_game, rating_games, points_produced, individual_possessions, individual_offensive_rating, individual_defensive_rating, formula_version
- `lake.marts.nba_player_season_stats`: person_id, first_name, last_name, season_start_year, season_label, game_type, is_competitive, primary_team_id, games_played, team_games_played, is_qualified, first_game_date, last_game_date, total_minutes, total_points, total_rebounds, total_assists, total_steals, total_blocks, total_turnovers, total_field_goals_made, total_field_goals_attempted, total_three_pointers_made, total_three_pointers_attempted, total_free_throws_made, total_free_throws_attempted, ts_points, ts_field_goals_attempted, ts_free_throws_attempted, efg_three_pointers_made, points_per_game, rebounds_per_game, assists_per_game, field_goal_pct, three_point_pct, free_throw_pct
- `lake.marts.nba_player_shot_zones`: person_id, first_name, last_name, season_start_year, season_label, game_type, shot_zone, shot_zone_order, field_goals_attempted, field_goals_made, field_goal_pct, field_goal_points, points_per_shot, share_of_attempts, avg_shot_distance_ft, league_field_goal_pct, league_points_per_shot, league_share_of_attempts, field_goal_pct_vs_league
- `lake.marts.nba_player_stint_advanced`: person_id, first_name, last_name, team_id, season_start_year, season_label, game_type, games_played, total_minutes, total_points, true_shooting_pct, effective_field_goal_pct, three_point_attempt_rate, free_throw_rate, true_shooting_points_added, usage_pct, turnover_pct, assist_pct, offensive_rebound_pct, defensive_rebound_pct, rebound_pct, steal_pct, block_pct, player_possessions, points_per_100, rebounds_total_per_100, assists_per_100, steals_per_100, blocks_per_100, turnovers_per_100, game_score_per_game, rating_games, points_produced, individual_possessions, individual_offensive_rating, individual_defensive_rating, formula_version
- `lake.marts.nba_players_dim`: person_id, first_name, last_name, player_name, has_bio_record, birth_date, height_inches, height_cm, height_feet_inches, body_weight_lbs, body_weight_kg, is_guard, is_forward, is_center, position, school, country, is_undrafted, draft_year, draft_round, draft_number, first_game_date, last_game_date, first_season_start_year, last_season_start_year, seasons_played, played_in_last_two_seasons, age_at_first_game, age_at_last_game
- `lake.marts.nba_seasons_dim`: season_start_year, season_label, season_first_game_date, season_last_game_date, regular_season_games, playoff_games, teams, min_team_regular_season_games, max_team_regular_season_games, is_current, coverage_tier, is_in_coverage
- `lake.marts.nba_team_advanced_profile`: team_id, season_start_year, season_label, game_type, games_played, wins, losses, possessions, offensive_rating, defensive_rating, net_rating, pace, effective_field_goal_pct, true_shooting_pct, assist_pct, rebound_pct, turnover_pct, three_point_attempt_rate, points_in_paint_share, fast_break_points_share, offensive_rebound_pct, free_throw_rate, opp_effective_field_goal_pct, opp_turnover_pct, defensive_rebound_pct, opp_free_throw_rate, margin_of_victory, pythagorean_wins, luck_wins, simple_rating_system, strength_of_schedule, relative_offensive_rating, relative_defensive_rating, relative_pace, relative_effective_field_goal_pct, relative_true_shooting_pct, games_with_counts, games_with_full_box, coverage_flag, formula_version
- `lake.marts.nba_team_dim`: team_id, current_team_city, current_team_name, current_full_name, current_team_abbrev, current_league, current_era_season_founded, current_era_active_till, franchise_first_season, franchise_era_count, has_relocated_or_renamed
- `lake.marts.nba_team_form`: team_id, game_id, season_start_year, game_type, game_date, last_10_games, last_10_net_rating, last_20_games, last_20_net_rating, season_to_date_games, season_to_date_net_rating, league_to_date_offensive_rating, league_to_date_pace, formula_version
- `lake.marts.nba_team_game_stats`: game_id, team_id, opponent_team_id, season_start_year, season_label, game_type, game_date, is_home, is_win, overtime_periods, team_minutes, points, opp_points, point_margin, field_goals_made, field_goals_attempted, three_pointers_made, three_pointers_attempted, free_throws_made, free_throws_attempted, rebounds_offensive, rebounds_defensive, rebounds_total, assists, steals, blocks, turnovers, fouls_personal, opp_field_goals_made, opp_field_goals_attempted, opp_three_pointers_made, opp_three_pointers_attempted, opp_free_throws_made, opp_free_throws_attempted, opp_rebounds_offensive, opp_rebounds_defensive, opp_rebounds_total, opp_assists, opp_steals, opp_blocks, opp_turnovers, opp_fouls_personal, possessions, pace, offensive_rating, defensive_rating, net_rating, effective_field_goal_pct, turnover_pct, offensive_rebound_pct, free_throw_rate, opp_effective_field_goal_pct, opp_turnover_pct, defensive_rebound_pct, opp_free_throw_rate, rebound_pct, three_point_attempt_rate, assist_pct, true_shooting_pct, counts_source, has_full_box, formula_version
- `lake.marts.nba_team_head_to_head`: team_id, opponent_team_id, games_played, wins, losses, win_pct, avg_points_for, avg_points_against, avg_point_margin, first_meeting_date, last_meeting_date
- `lake.marts.nba_team_season_summary`: team_id, season_start_year, season_label, games_played, wins, losses, home_wins, away_wins, total_points_for, total_points_against, win_pct, points_for_per_game, points_against_per_game, point_margin_per_game
- `lake.marts.nba_team_seasons_dim`: team_id, season_start_year, season_label, team_city, team_name, team_full_name, team_abbrev
