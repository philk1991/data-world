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
- Percentage columns (`*_pct`, ratings, shares) are stored as 0–1 fractions
  unless the column name says otherwise. Multiply by 100 only when presenting.
- Many advanced/box-score columns are `NULL` for older games (stats were not
  recorded pre-modern era, and advanced metrics only start ~1996). Filter out
  NULLs when ranking, and mention the coverage caveat when it matters.
- To resolve a `team_id` to a readable name, join to `nba_team_dim`
  (`current_full_name`). To resolve a `person_id` to a name, use the
  `first_name` / `last_name` columns already present on the player marts.

## Table grain (pick the right one)

- `nba_game_results` — one row per game (`game_id`); home/away box scores pivoted
  onto one row. Use for single-game questions, margins, attendance, arenas.
- `nba_player_career_stats` — one row per player (`person_id`); traditional
  career totals, per-game averages, shooting splits over competitive games
  (regular season + playoffs + play-in + Cup final, combined). Use for career
  leaders; for regular-season-only careers, sum the Regular Season rows of
  `nba_player_season_stats`.
- `nba_player_advanced_career` — one row per player; minutes-weighted advanced
  efficiency (usage, TS%, ratings, PIE) and double/triple-double counts over
  competitive games, like `nba_player_career_stats`. Advanced-stats era only
  (~1996+).
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
  100 for a regular season) before ranking by percentage.
- `nba_player_clutch_stats` — one row per (`person_id`, `season_start_year`,
  `game_type`), 1996-97 on. Clutch time = the last 5 minutes of the 4th quarter
  or overtime with the score within 5. Clutch points, shooting splits,
  `clutch_true_shooting_pct` against the season's all-minutes
  `true_shooting_pct`, rebounds, turnovers and `clutch_go_ahead_field_goals`.
  Use for "best clutch scorer", "most go-ahead shots", "who shoots better in
  the clutch". No assists, steals or blocks. **Set a minimum
  `clutch_field_goals_attempted`** (e.g. 30) before ranking by percentage.
- `nba_team_season_summary` — one row per (`team_id`, `season_start_year`);
  regular-season record, home/away wins, scoring. Use for standings / best
  record questions.
- `nba_team_advanced_profile` — one row per (`team_id`, `season_start_year`);
  season advanced efficiency (offensive/defensive/net rating, pace, four-factor).
  Coverage starts ~1996.
- `nba_players_dim` — one row per player (`person_id`); biography (birth date,
  height, weight, position, draft, school, country) and the span of competitive
  games played. Join it to the player stats marts for age or physical profile.
  Height and weight are a single current listing, not per-season values;
  box-score-only players (`has_bio_record` false) have null bio columns.
- `nba_team_dim` — one row per `team_id`; the franchise's current identity
  (`current_full_name`, `current_team_abbrev`) plus relocation/rename history.
  This is the name lookup dimension.
- `nba_team_head_to_head` — one row per ordered (`team_id`, `opponent_team_id`);
  all-time competitive record from `team_id`'s perspective (the reverse matchup
  is a separate row).

## Key definitions

- **Season derivation**: `season_start_year` comes from the game id — the
  league's own assignment — so the 2020 bubble games belong to 2019-20 and the
  July 2021 Finals to 2020-21. `season_start_year = 2023` is the "2023-24"
  season; `season_label` gives the readable form. Never derive a season from the
  raw calendar year of a spring game.
- **"This season" / "current season" / "so far"**: the latest
  `season_start_year` that has Regular Season games
  (`SELECT max(season_start_year) FROM lake.marts.nba_game_results WHERE
  game_type = 'Regular Season'`), not the latest completed season. Always filter
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
  Cup Final). Team summary/profile marts are Regular Season only; head-to-head counts
  competitive meetings only (Regular Season, Playoffs, Play-in Tournament, NBA
  Cup Final — no Preseason or All-Star).
- **"Games played" counts only games actually played** (recorded minutes) on the
  player marts.
- **Qualified players**: for per-game or percentage leaderboards on
  `nba_player_season_stats`, filter `is_qualified` (at least 70% of
  `team_games_played`, Regular Season only) rather than a fixed games minimum,
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
- `lake.marts.nba_player_advanced_career`: person_id, first_name, last_name, is_guard, is_forward, is_center, games_with_advanced, minutes_per_game, double_doubles, triple_doubles, usage_pct, true_shooting_pct, effective_field_goal_pct, offensive_rating, defensive_rating, net_rating, assist_pct, rebound_pct, player_impact_estimate
- `lake.marts.nba_player_career_stats`: person_id, first_name, last_name, is_guard, is_forward, is_center, draft_year, height_inches, first_game_date, last_game_date, games_played, total_points, total_rebounds, total_assists, total_steals, total_blocks, total_turnovers, points_per_game, rebounds_per_game, assists_per_game, career_field_goal_pct, career_three_point_pct, career_free_throw_pct
- `lake.marts.nba_player_clutch_stats`: person_id, first_name, last_name, season_start_year, season_label, game_type, clutch_games, clutch_points, clutch_points_per_game, clutch_field_goals_made, clutch_field_goals_attempted, clutch_field_goal_pct, clutch_three_pointers_made, clutch_three_pointers_attempted, clutch_three_point_pct, clutch_free_throws_made, clutch_free_throws_attempted, clutch_free_throw_pct, clutch_true_shooting_pct, true_shooting_pct, clutch_rebounds, clutch_turnovers, clutch_go_ahead_field_goals
- `lake.marts.nba_player_game_stats`: person_id, game_id, first_name, last_name, game_date, season_start_year, season_label, game_type, player_team_id, opponent_team_id, is_home, is_win, is_starter, starting_position, minutes_played, points, rebounds_offensive, rebounds_defensive, rebounds_total, assists, steals, blocks, turnovers, fouls_personal, field_goals_made, field_goals_attempted, field_goal_pct, three_pointers_made, three_pointers_attempted, three_point_pct, free_throws_made, free_throws_attempted, free_throw_pct, plus_minus_points, usage_pct, true_shooting_pct, effective_field_goal_pct, offensive_rating, defensive_rating, net_rating, assist_pct, rebound_pct, player_impact_estimate, is_double_double, is_triple_double
- `lake.marts.nba_player_season_stats`: person_id, first_name, last_name, season_start_year, season_label, game_type, primary_team_id, games_played, team_games_played, is_qualified, total_points, total_rebounds, total_assists, total_steals, total_blocks, total_turnovers, total_field_goals_made, total_field_goals_attempted, total_three_pointers_made, total_three_pointers_attempted, total_free_throws_made, total_free_throws_attempted, points_per_game, rebounds_per_game, assists_per_game, field_goal_pct, three_point_pct, free_throw_pct
- `lake.marts.nba_player_shot_zones`: person_id, first_name, last_name, season_start_year, season_label, game_type, shot_zone, shot_zone_order, field_goals_attempted, field_goals_made, field_goal_pct, field_goal_points, points_per_shot, share_of_attempts, avg_shot_distance_ft, league_field_goal_pct, league_points_per_shot, league_share_of_attempts, field_goal_pct_vs_league
- `lake.marts.nba_players_dim`: person_id, first_name, last_name, player_name, has_bio_record, birth_date, height_inches, height_cm, height_feet_inches, body_weight_lbs, body_weight_kg, is_guard, is_forward, is_center, position, school, country, is_undrafted, draft_year, draft_round, draft_number, first_game_date, last_game_date, first_season_start_year, last_season_start_year, seasons_played, played_in_last_two_seasons, age_at_first_game, age_at_last_game
- `lake.marts.nba_team_advanced_profile`: team_id, season_start_year, season_label, games_played, offensive_rating, defensive_rating, net_rating, pace, effective_field_goal_pct, true_shooting_pct, assist_pct, rebound_pct, turnover_pct, three_point_attempt_rate, points_in_paint_share, fast_break_points_share
- `lake.marts.nba_team_dim`: team_id, current_team_city, current_team_name, current_full_name, current_team_abbrev, current_league, current_era_season_founded, current_era_active_till, franchise_first_season, franchise_era_count, has_relocated_or_renamed
- `lake.marts.nba_team_head_to_head`: team_id, opponent_team_id, games_played, wins, losses, win_pct, avg_points_for, avg_points_against, avg_point_margin, first_meeting_date, last_meeting_date
- `lake.marts.nba_team_season_summary`: team_id, season_start_year, season_label, games_played, wins, losses, home_wins, away_wins, total_points_for, total_points_against, win_pct, points_for_per_game, points_against_per_game, point_margin_per_game
