---
name: cube-develop
description: Scaffold a new Cube semantic-layer model (cube/model/cubes/<mart>.yml) on top of an existing dbt mart. Prompts the user for which dbt mart to build on and which metrics to create, suggests dimensions/measures from the mart's dbt documentation, and keeps the cube's descriptions and grain aligned with the dbt model. Use whenever the user wants to add a Cube model, expose a dbt mart in Cube or Cube Playground, or define metrics/dimensions on top of a mart.
---

# cube-develop

Scaffold a new Cube model that exposes an existing dbt mart, following the
conventions the hand-written `nba_game_results`, `nba_team_dim`,
`spotify_top_artists` and `spotify_top_tracks` cubes already use. The goal is
that the new cube reads like it was written by the same person: same
description style, same instinct for which columns become dimensions vs.
measures, same YAML shape.

Read [references/conventions.md](references/conventions.md) in full before
writing any YAML — it holds the exact rules (description-alignment algorithm,
dimension/measure heuristics, type mapping, formatting) that this file only
summarizes.

## Step 1 — Ask which mart to build on

If the user named a mart, use it. Otherwise list the candidates:

```bash
source .venv/bin/activate
python .claude/skills/cube-develop/scripts/introspect_mart.py --list
```

This prints every mart model with its domain and whether it already has a
cube file. Prompt the user with the marts that don't have one yet, grouped by
domain, and let them pick. If they pick a mart that already has a cube,
confirm whether they want to revise the existing one rather than starting
over — read it first if so.

## Step 2 — Introspect the mart (don't guess)

```bash
python .claude/skills/cube-develop/scripts/introspect_mart.py <mart_name>
```

This is the single source of truth for Step 3 — it returns the dbt
description, `meta` (grain, purpose, business_question, seasonality,
relationships), every column's dbt description, and the column's *actual*
DuckDB type from a live `DESCRIBE` against the real table (never inferred
from the column name). It also warns about any mismatch between what dbt
documents and what the table actually has — surface those to the user if any
appear, since they usually mean the dbt YAML is stale.

If it errors because `manifest.json` is missing, tell the user to run
`task dbt:compile` first and stop.

## Step 3 — Propose dimensions and measures, then ask

Using the introspection output and
[references/conventions.md](references/conventions.md), draft a candidate
list:

- **Dimensions**: identifiers, dates, categoricals, booleans, rank-like
  numbers. Mark the column(s) implied by `meta.grain` as `primary_key: true`
  (composite grain → multiple primary keys). Leave out ingestion/audit
  columns (`ingested_at`) and fine-grained numeric detail that's better
  rolled into a measure.
- **Measures**: always `count` first. Then, per numeric column, use its dbt
  description to judge `avg` (per-game/rate/percentage), `sum` (career or
  dataset totals), or `max`/`min` (a ceiling/floor stat worth knowing on its
  own) — see the conventions file for the exact reasoning and phrasing
  pattern. Propose computed rate measures (`CASE WHEN ... END` over `avg`)
  for boolean flags where a win-rate-style metric makes sense — and if the
  column instead has several possible values (an `accepted_values` test),
  propose one rate per value, not just one. Watch for point-in-time columns
  bounded by a time column in the same row (an opening/closing price) —
  those need `MIN_BY`/`MAX_BY` keyed on time, not `avg`, or they'll silently
  produce wrong numbers once someone queries at a coarser time granularity
  than the mart's native grain. The conventions file has the worked example.

Present this as a short table (dimension/measure name, type, source column,
one-line description, include? y/n) and ask the user to confirm, add, or drop
entries — this is the "which metrics to create" prompt the skill exists for.
Don't skip it even if your defaults look obviously right; the user may know a
downstream dashboard need that the dbt docs don't capture.

## Step 4 — Write the cube YAML

First decide the cube's `name:` (and file name) — it is **not** always the
mart name. Per
[references/conventions.md](references/conventions.md#file-and-table-naming):
if the mart name already reads as belonging to its domain (`nba_*`, `sb_*`),
keep the cube name identical to it. Otherwise (crypto, payments, and any
future domain without its own prefix) give the cube a domain-prefixed name
and drop redundant qualifiers, the way `top_artists_by_period` became
`spotify_top_artists`. `sql_table:` is unaffected either way — always the
mart's exact table name from Step 2's introspection output, verbatim.

Write `cube/model/cubes/<cube_name>.yml` following the template and spacing
in [references/conventions.md](references/conventions.md#file-layout-template)
exactly:

- `sql_table: marts.<mart_name>` (flat `marts` schema, no domain prefix —
  this is the table name, independent of whatever you chose for `name:`).
- Top-level `description: >` — adapted per the description-alignment rules,
  not a verbatim copy of the dbt description.
- Dimensions and measures from Step 3, in the same order the columns appear
  in the dbt model.

If Step 2 reported `cube_file_exists: true`, read that existing file first
and preserve any hand-written measures the user wants to keep — merge, don't
overwrite.

## Step 5 — Validate

There's no `cube:validate` task. At minimum:

1. Parse the YAML you just wrote (`python3 -c "import yaml; yaml.safe_load(open('cube/model/cubes/<mart>.yml'))"`) to catch syntax errors.
2. Cross-check every `sql:` value against the `duckdb_columns` list from
   Step 2's introspection output — a typo here fails silently in Cube until
   someone queries it.

Offer to start `task cube:dev` so the user can see it load in Playground
(http://localhost:4000), but warn them first: the DuckDB driver opens
`data/spotify.duckdb` read-write with no read-only mode, so it must not run
at the same time as `task dbt:run` or an ingest job. If they say yes, start it
in the background, watch for a clean startup vs. a schema-compile error, then
leave it running (or stop it, per their preference) rather than guessing.

## Step 6 — Hand off

Tell the user: the file you wrote, the dimensions/measures included, and how
to see it (`task cube:dev` → Playground). If more marts in the same domain
still lack a cube, mention them as an obvious next step.
