# ADR 0003: Seasons before 1954-55

Status: accepted (10 Nov 2026)

## Context

The source holds only the 30 current franchises, so every game against a defunct team is missing. 1946-47 has 18 games across 3 teams; full schedules only start in 1954-55. Careers, standings and early "qualified" leaderboards were silently built on partial seasons.

## Decision

Exclude seasons before 1954-55 by default. The cutoff is the dbt var `nba_first_complete_season` (1954), read through the `nba_first_complete_season()` macro and exposed as `nba_seasons_dim.coverage_tier` / `is_in_coverage`.

- Career marts leave those seasons out and flag careers that started earlier (`has_games_before_coverage`).
- Cube excludes them from its cubes.
- nao excludes them unless a question asks for them.
- Game and season marts keep the rows, tagged through `nba_seasons_dim`, so nothing is lost for exploration.

## Consequences

Players whose careers began before 1954-55 (George Mikan, Dolph Schayes) show partial career totals, flagged. Changing the cutoff is a one-line var change and a rebuild.
