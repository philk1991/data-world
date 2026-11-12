# ADR 0002: What lives in dbt and what lives in Cube

Status: accepted (10 Nov 2026). Design and research: `plans/nba-staff-ae-project.md`, Part 2.

## Context

Ratios were defined in both dbt and Cube. Cube's true shooting re-implemented the dbt formula over season totals that could not support it, and returned 6,136% for a 1946-47 season. Formulas drifted because each tool owned some of them.

## Options

A. Thick marts, thin Cube: dbt pre-computes every metric at fixed grains.
B. Components in dbt, metrics in Cube.
C. MetricFlow in dbt as the single source of metric definitions.
D. B with Cube files generated from dbt metadata.

## Decision

Option B. The boundary rule: if a value can be rebuilt from additive columns by a sum over sum, dbt stores the parts and Cube owns the ratio. If it can't (SRS, Oliver ratings, as-of form, league baselines), dbt computes it at its natural grain, tags it non-additive, and Cube exposes it without re-aggregating it. Row-level flags (`is_qualified`, `is_competitive`, coverage) live in dbt; segments and default scopes live in Cube. Cubes become private and views are the published interface. D is a later step once the Cube model settles; C stays a spike in case Cube is ever dropped.

## Consequences

- Marts expose matched components (`ts_points`, `ts_field_goals_attempted`, `ts_free_throws_attempted`, `efg_three_pointers_made`, …) alongside any convenience rates.
- Cube rate measures divide sums of those components; no formula constant appears in both dbt and Cube.
- The tag is `config.meta.additive` (true or false) on every fact mart, with `meta.non_additive_columns` listing what can't be re-aggregated; `task cube:additivity:check` enforces it and blocks Cube measures that sum or average those columns. `task cube:reconcile` checks that the kept rollup marts equal the Cube views row for row.
- nao asks Cube for defined metrics (ADR 0005).
