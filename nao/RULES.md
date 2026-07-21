# nao agent rules — NBA marts

You are a data analyst answering natural-language questions about NBA data by
writing DuckDB SQL against the `marts` schema of this warehouse. Only the eight
`marts.nba_*` tables are in scope. Prefer these curated marts over any raw or
staging tables.

## General guidance

- Write standard DuckDB SQL. Fully qualify tables as `marts.<table>`.
- The marts are the analysis-ready layer — do not attempt to join back to
  `raw_*` or `stg_*` tables; everything needed is in `marts.nba_*`.
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
  career totals, per-game averages, shooting splits. Use for career leaders.
- `nba_player_advanced_career` — one row per player; minutes-weighted advanced
  efficiency (usage, TS%, ratings, PIE) and double/triple-double counts.
  Advanced-stats era only (~1996+).
- `nba_player_season_stats` — one row per (`person_id`, `season_start_year`,
  `game_type`). Use for season-level questions and regular-season-vs-playoff
  splits. **Filter `game_type = 'Regular Season'`** for "led the league"-style
  questions unless playoffs are explicitly requested.
- `nba_team_season_summary` — one row per (`team_id`, `season_start_year`);
  regular-season record, home/away wins, scoring. Use for standings / best
  record questions.
- `nba_team_advanced_profile` — one row per (`team_id`, `season_start_year`);
  season advanced efficiency (offensive/defensive/net rating, pace, four-factor).
  Coverage starts ~1996.
- `nba_team_dim` — one row per `team_id`; the franchise's current identity
  (`current_full_name`, `current_team_abbrev`) plus relocation/rename history.
  This is the name lookup dimension.
- `nba_team_head_to_head` — one row per ordered (`team_id`, `opponent_team_id`);
  all-time competitive record from `team_id`'s perspective (the reverse matchup
  is a separate row).

## Key definitions

- **Season derivation**: the NBA season spans Oct–Apr, so games before July
  belong to the prior start year. `season_start_year = 2023` is the "2023-24"
  season; `season_label` gives the readable form. Never derive a season from the
  raw calendar year of a spring game.
- **Mid-season trades**: in `nba_player_season_stats` a traded player is combined
  into one row per game type; `primary_team_id` is the team they played the most
  games for that season. Do not expect a separate row per team.
- **game_type splits**: `nba_player_season_stats` splits by `game_type`
  (Regular Season, Playoffs, Play-in Tournament, Preseason, All-Star Game, NBA
  Cup, …). Team summary/profile marts are Regular Season only; head-to-head is
  Regular Season + Playoffs only.
- **"Games played" counts only games actually played** (recorded minutes) on the
  player marts.
- **Per-game vs totals**: player marts expose both `total_*` and `*_per_game`.
  Use `points_per_game` for "points per game" / scoring-average questions, not
  `total_points / games_played` recomputed by hand.
