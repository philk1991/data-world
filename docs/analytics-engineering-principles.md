# Analytics engineering principles

These are the rules the NBA models follow across dbt, Cube and nao, so that one
question gets one answer wherever it is asked. They came out of the NBA
consistency project (`plans/nba-staff-ae-project.md`), which found three
different answers to "LeBron James's career points" and a Cube true shooting
of 6,136%. Each principle says what to do, why, and what enforces it. The
architecture decisions behind them are the ADRs in `plans/adr/`.

The NBA domain is the reference implementation. Other domains should follow the
same rules as they grow a semantic layer.

## 1. Store additive components; compute ratios at query time

A ratio can't be added up. Averaging a rate across rows, or recomputing it from
totals that were filtered differently, gives the wrong number. So dbt stores
the parts of every rate as columns that can be summed, and Cube divides their
sums at whatever grain the query asks for.

- True shooting is `SUM(ts_points) / (2 × (SUM(ts_field_goals_attempted) + 0.44 × SUM(ts_free_throws_attempted)))`.
  The `ts_*` columns only count games where both attempt counts were recorded,
  so the parts always match.
- Player rates such as usage, assist % and rebound % are numerator and
  opportunity pairs on `nba_player_game_stats` (`usage_opportunity_numerator`,
  `usage_opportunity`, …). They come from the `nba_shooting_components` and
  `nba_player_rate_components` macros, so they are correct over any set of
  games: a season, a career, the games against one opponent.
- Team and league possessions are sums of per-game estimates, not one estimate
  made from season totals, because only the sum can be added up.

**Why:** the 6,136% bug was Cube dividing made shots summed over every game by
attempts summed only over games where attempts were recorded.
**Enforced by:** ADR 0002, and `task cube:reconcile` (principle 4).

## 2. Write each formula once per layer

Each rate formula has exactly one definition in each layer:

| Layer | Where | Used for |
| --- | --- | --- |
| dbt | `dbt/macros/nba_metrics.sql` (`nba_ts`, `nba_efg`, `nba_tov_pct`, `nba_plays`, …) | the rollup and non-additive marts |
| Cube | `cube/model/macros/nba_rates.jinja` (`true_shooting`, `effective_fg`, `turnover_pct`, `per_100`, `pace`, `ts_attempts`) | every Cube measure |
| nao | none | nao reads the columns or asks Cube |

Cube cubes import the macros through Jinja. The import sits inside a YAML
comment on the first line, so the raw file still parses as YAML:

```yaml
# {% import "macros/nba_rates.jinja" as rates %}
cubes:
  - name: ...
    measures:
      - name: true_shooting_pct
        sql: "{{ rates.true_shooting('SUM({CUBE}.ts_points)', 'SUM({CUBE}.ts_field_goals_attempted)', 'SUM({CUBE}.ts_free_throws_attempted)') }}"
```

**Why:** before this, true shooting was written out in eight places (four in
Cube, four in dbt), and the 6,136% bug lived in one of the hand-typed copies. With one definition, a fix
happens once, and a new cube (the shot view) gets the formula right by calling
it. dbt keeps its own copy because the rollup marts stay (ADR 0004), and the
reconciliation proves the two copies agree.
**Enforced by:** `task cube:formulas:check`. It fails on a formula constant
(`0.44`, `0.5 *`, `48 *`) anywhere else in dbt SQL, Cube `sql` values or nao's
rules and docs.

## 3. Tag what can't be added up

Some values can't be split into components: SRS (solved by iteration), rolling
form, league baselines, and rates whose components live in another model. They
stay in dbt at their natural grain. Every NBA fact mart declares
`config.meta.additive`:

- `true`: every rate or average in the mart can be rebuilt from its own
  additive columns.
- `false`: `meta.non_additive_columns` lists the columns that must never be
  summed or averaged across rows.

Cube exposes non-additive values only as dimensions, or in weighted measures
(the vs-league ratings are weighted by possessions), never in a `sum` or `avg`.
SRS, strength of schedule and Pythagorean wins reach the `team_season` view this
way.

**Why:** a value that looks like a number invites `AVG()`. The tag makes the
rule visible to people, to nao (its generated `nba_marts.md` states each
table's additivity) and to the checks.
**Enforced by:** `task cube:additivity:check`. It fails on a fact mart without
the tag, or on a Cube measure that sums or averages a listed column.

## 4. Rollups are conveniences: reconcile them, don't trust them

The season and career marts (`nba_player_season_stats`,
`nba_player_career_stats`, the advanced marts, the team profile, the league
baselines, shot zones, clutch) are kept for SQL users (ADR 0004). Cube computes
the same numbers from the facts. The two must agree on every row.

**Why:** the first run of the reconciliation found four real bugs that had
passed every other test, including per-game averages that were wrong for every
season before the 1980s (principle 6).
**Enforced by:** `task cube:reconcile` (`cube/scripts/reconcile_marts.py`).
It compares eight view and mart pairs row by row, about 200,000 rows, with a
1e-9 tolerance, and reports rows missing on either side. It needs `task cube:dev`
running. Run it after changing a mart or a measure.

## 5. Store full precision; round only for display

Marts store unrounded values. Cube measures carry a display format (d3:
`.3f` for rates, `.1f` for per-game stats, ratings and pace, `,.0f` for
counts). The MCP server passes the format to Claude, and nao's rules say to
round in the answer, never in SQL before aggregating.

**Why:** rounded columns flipped by 0.1 between builds with identical data
(floating-point summation order at a .x5 boundary), and summing rounded values
compounds the error. Unrounded marts are also what makes a 1e-9 reconciliation
tolerance possible.
**Exceptions:** parsing logic (overtime periods, mm:ss minutes), unit
conversions (cm and kg) and the SRS solver.

## 6. A blank is not a zero

Old box scores often leave stats unrecorded: half the 1950s player-games have
no assists. A missing value must stay null and stay out of both the numerator
and the denominator.

- Each component is null before its stat's coverage season (assists 1964-65,
  rebound splits, steals and blocks 1973-74, turnovers 1977-78, threes
  1979-80), set once in the component macros, so no consumer repeats the years.
- Per-game averages divide by the games where the stat was recorded
  (`games_with_rebounds`, `games_with_assists`, …), not `games_played`. This
  moved Bill Russell's career rebounds from 22.0 to 22.5 a game, which matches
  the official record.
- Rates whose inputs didn't exist are null, not 0: team three-point attempt
  rate before 1979-80 divides by `three_par_field_goals_attempted`, which is
  null before then.

**Why:** dividing a partial total by every game understates the average,
silently and only for old eras, which is the hardest kind of error to spot.

## 7. Decide scope once; apply it everywhere

Scope decisions are made once, recorded, and applied by every reader:

- A career is the Regular Season by default, with Playoffs as the alternative,
  and the two add up (ADR 0001).
- Seasons before 1954-55 are left out of careers and Cube (ADR 0003). The cutoff
  is one dbt var, `nba_first_complete_season`, exposed through
  `nba_seasons_dim.is_in_coverage`.
- Season labels, competitive and career game types, and coverage years are
  macros in `dbt/macros/nba_scope.sql`.
- Cube views apply the default scope as `default_filters`: Regular Season until
  a query filters `game_type`. nao's rules carry the same defaults.

**Why:** the three career-points answers were three scopes (regular season,
competitive games, every game) that nobody had chosen between.

## 8. One published interface

The NBA cubes are private (`public: false`). The views in
`cube/model/views/nba.yml` are what BI tools, the MCP server and agents see.
Each view's description states its grain, default scope, coverage and
caveats. Cube 1.8.8 has no `ai_context`, so the descriptions carry the agent
guidance.

**Why:** an agent picks members by name and description. A smaller surface
with explicit grain and scope gives fewer wrong joins and fewer wrong defaults.

## 9. Conformed dimensions, named as of the time

Shared dimensions are built once and joined by every fact: `nba_seasons_dim`,
`nba_game_types_dim`, `nba_players_dim`, `nba_team_dim` (the franchise today)
and `nba_team_seasons_dim` (the team's name that season).

**Why:** the 2007-08 franchise is the Seattle SuperSonics in 2007-08, not the
Oklahoma City Thunder. History should read as it happened.

## 10. Describe once; let the description travel

A column's description is written once in dbt and flows everywhere:

- Columns shared by several models take a doc block from
  `dbt/models/docs/nba.md`.
- `persist_docs` writes descriptions into the lake as table and column comments.
- `task cube:docs:sync` copies them onto the Cube dimensions that expose a
  column as-is.
- `task nao:sync` writes them into nao's context and generates
  `nao/docs/nba/nba_marts.md`.

Fix a description in dbt, never downstream.
**Enforced by:** `task dbt:docs:check` and `task cube:docs:check`.

## 11. Document upstream defects; don't patch them silently

When the source is wrong and the fix belongs upstream, record it where every
reader will see it, and report it to the publisher. Don't invent data.

**Example:** the Kaggle source is missing six 2024-25 games or records them
0-0, so ten teams show 81 games and San Antonio 80. One doc block
(`nba__upstream_gap_2024_25`) carries the caveat into seven model
descriptions, the lake comments, the Cube view descriptions and nao's rules,
and a report was drafted for the dataset's maintainer.

## 12. Write decisions down; let checks hold the line

Decisions go in ADRs (`plans/adr/`) or the metrics decision log
(`plans/nba-advanced-metrics-decision-log.md`), with the reason and the cost.
A rule that matters gets a check, so it survives the next person, or the next
agent, who doesn't know it.

| Check | What it guards |
| --- | --- |
| `task dbt:build:select` (data and unit tests) | correctness of each model, coverage rules, closed seasons complete |
| `task dbt:lint` | SQL style (SQLFluff) |
| `task dbt:docs:check` | shared columns described once (principle 10) |
| `task cube:docs:check` | Cube descriptions match dbt (principle 10) |
| `task cube:additivity:check` | non-additive columns never aggregated (principle 3) |
| `task cube:formulas:check` | one formula definition per layer (principle 2) |
| `task cube:reconcile` | rollup marts equal Cube, row by row (principle 4) |
| `task cube:mcp:check` | the MCP server can describe and query the views |

## Checklist: adding an NBA metric

1. **Can it be rebuilt as a sum over a sum?** If yes, add the components to
   the fact (`nba_player_game_stats`, `nba_team_game_stats` or
   `nba_shot_events`), null before the stat's coverage season, through the
   component macros. If no, compute it in dbt at its natural grain and add it
   to the mart's `non_additive_columns`.
2. **Write the formula once:** in `nba_metrics.sql` if a mart needs it, and in
   `nba_rates.jinja` for Cube.
3. **Add the Cube measure** on the private cube, calling the macro, with a
   display format and a description that states the weighting and coverage.
   Expose it through a view.
4. **Document the columns** in dbt (a doc block if the column is shared), then
   run `task cube:docs:sync` and `task nao:sync`.
5. **If a rollup mart carries it too,** add the pair to `reconcile_marts.py`.
6. **Run the checks:** the dbt build, `dbt:docs:check`, `cube:docs:check`,
   `cube:additivity:check`, `cube:formulas:check` and `cube:reconcile`.
