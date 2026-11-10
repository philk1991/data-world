# ADR 0001: What "career" means

Status: accepted (10 Nov 2026)

## Context

The review found three answers to "LeBron's career points": 52,142 from `nba_player_career_stats` (every competitive game), 53,916 from Cube (every game type, preseason and All-Star included) and 43,522 for the regular season, the figure NBA.com and Basketball-Reference publish. Nothing defined which was meant.

## Options

1. Every competitive game (regular season, play-in, playoffs, Cup final) in one row: what the mart did.
2. Regular season only.
3. Regular season by default, playoffs as a separate scope, each on its own row so they add up.

## Decision

Option 3. A career is reported per scope, `game_type` Regular Season (the default) or Playoffs, one row each. Totals add across the two rows, and rates are recomputed from the summed made/attempted columns, so a combined career is always available without a third definition. Play-in and NBA Cup final games count toward neither, as on NBA.com.

## Consequences

- `nba_player_career_stats` and `nba_player_advanced_career` change grain from one row per player to one row per `(person_id, game_type)`. Anyone selecting a single career line must filter `game_type = 'Regular Season'`.
- The scope list lives in one macro, `nba_career_game_types()`, and in `nba_game_types_dim.is_career`.
- Cube career measures (Phase 3) and nao's rules use the same default.
