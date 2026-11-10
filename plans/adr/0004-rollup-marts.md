# ADR 0004: Rollup marts become convenience tables

Status: accepted (10 Nov 2026)

## Context

Season and career rollups (`nba_player_season_stats`, `nba_player_career_stats`, `nba_player_season_advanced`, `nba_player_advanced_career`, `nba_team_season_summary`) are useful to SQL users and nao, but under ADR 0002 Cube owns aggregation.

## Decision

Keep them as convenience tables, built so they reconcile by construction and tested against their sources:

- `nba_player_season_stats` and `nba_player_game_stats` share `int_nba_player_games`, so the season rows add up from the game rows exactly.
- `nba_player_career_stats` is a sum of `nba_player_season_stats` rows.
- `nba_player_season_advanced` reads `primary_team_id`, `team_games_played` and `is_qualified` from `nba_player_season_stats`, so the two can't disagree.
- `assert_nba_career_reconciles_with_seasons` guards the career rollups; Phase 3 adds reconciliation against Cube.

Existing `nba_<entity>` names stay; no `fct_`/`dim_` rename, which would break Cube, nao and the field guide for no analytical gain.

## Consequences

Two paths to a season total exist (mart and Cube), so Phase 3's reconciliation tests are what keep them honest.
