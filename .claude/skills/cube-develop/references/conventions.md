# Cube model conventions

Derived from the existing hand-written cubes (`nba_game_results`, `nba_team_dim`,
`spotify_top_artists`, `spotify_top_tracks`). Match these exactly — the point of
this skill is that a new cube looks like it was written by the same person who
wrote the last one.

## File and table naming

`sql_table: marts.<mart_name>` is always the dbt mart's exact table name,
unchanged — always the flat `marts` schema, never `marts_<domain>`. Every
domain's `dbt_project.yml` entry sets `+schema: marts` regardless of which
subdirectory the model lives in, so the domain folder name never appears in
the table reference. **Never** guess this — take it verbatim from
`introspect_mart.py`'s output.

The cube's **`name:`** (and hence the file name, `cube/model/cubes/<name>.yml`)
is a different question and does *not* always equal the mart name:

- `nba_game_results` mart → cube name `nba_game_results` (unchanged), because
  the mart itself already carries a domain prefix (`nba_`). Same for StatsBomb
  (`sb_`).
- `top_artists_by_period` mart → cube name `spotify_top_artists` — the mart
  name has no domain hint on its own, so the cube layer adds one. Note this
  isn't a mechanical prefix-and-done: `_by_period` was also dropped as a
  redundant qualifier, since the cube's own docs already make clear it's a
  point-in-time comparison across periods.

So: check whether the mart name already reads as belonging to its domain
(does it start with the domain or a recognized abbreviation of it — `nba_`,
`sb_`?). If yes, keep the cube name identical to the mart name. If no (crypto's
`ohlcv_1h`/`ohlcv_1m`, payments' `payment_status`/`payments_by_minute`, and any
future domain without its own prefix convention), prefix the cube name with
the domain (`crypto_ohlcv_1h`) and drop any qualifier that's redundant once
the cube is named — use judgment here the way `spotify_top_artists` did,
don't just default to `<domain>_<mart_name>` unexamined.

`introspect_mart.py` finds a mart's existing cube (if any) by reading every
cube file's `sql_table`, not by matching filenames — because of the above,
filename-matching silently misses the Spotify cubes. Always trust its
`cube_file_exists` / `existing_cube_file` fields; never re-derive existence by
guessing a filename yourself.

## Description alignment

The cube's top-level `description` is the dbt model's description, adapted —
not copied blindly:

1. Start from the dbt model's `description` field.
2. Drop any trailing sentence that's about *query default ordering*
   (e.g. "Ordered by game_date descending.") — that's an implementation detail
   of the dbt model, meaningless to someone building a Cube query.
3. If the dbt `meta.seasonality` field exists and isn't already covered by the
   body, fold in the useful part of it (see `spotify_top_artists`, which turns
   dbt's `seasonality` note into "A point-in-time snapshot from the last
   ingest.").
4. If `meta.relationships` shows this mart deliberately does *not* need a join
   (e.g. a dimension mart that already has denormalized names elsewhere), say
   so explicitly — see `nba_team_dim`'s "Standalone cube — not joined to
   nba_game_results, which already carries denormalized home/away team names."
   This saves the next person from wiring up a join that isn't needed.

Use the YAML folded block scalar (`description: >`) with a blank line after it
before `dimensions:`, matching the existing files exactly.

## Choosing dimensions

Not every dbt column becomes a dimension. Include:

- All identifier/key columns (`*_id`, natural keys).
- Date/timestamp columns.
- Low/moderate-cardinality strings and categoricals (team names, genres,
  competition names, statuses).
- Booleans and boolean-like flags.
- Numeric columns that are themselves labels rather than quantities to
  aggregate (e.g. a rank).

Always exclude:

- Ingestion/audit columns (`ingested_at` and similar) — never appear as
  dimensions in any existing cube.
- Fine-grained numeric detail columns that exist in dbt purely to be summed or
  averaged elsewhere (e.g. `home_field_goals_made`, `home_rebounds_total` in
  `nba_game_results` — present in the dbt model, absent as dimensions; they
  only show up rolled into `avg_home_score` / `avg_point_margin` measures).
  If in doubt, ask: "would someone GROUP BY this, or aggregate it?" — the
  former is a dimension, the latter a measure.

`sql:` is the bare column name (identical to the dbt column name) unless a
dimension is computed.

## Primary key from grain

The dbt model's `meta.grain` field states the grain in prose (e.g.
"one row per team_id" or "one row per (team_id, season_start_year)"). Map it
directly:

- Single-column grain → that one dimension gets `primary_key: true`.
- Composite grain → mark **every** column in the tuple `primary_key: true`.
  Cube supports composite primary keys this way; don't try to synthesize a
  concatenated key column that doesn't exist in the dbt model.

## Type mapping

Cube types come from the *live DuckDB table* (via `DESCRIBE`), not guessed
from the column name — `scripts/introspect_mart.py` does this lookup. Mapping:

| DuckDB type contains | Cube type |
|---|---|
| `TIMESTAMP`, `DATE`, `TIME` | `time` |
| `BOOL` | `boolean` |
| `INT`, `FLOAT`, `DOUBLE`, `DECIMAL`, `NUMERIC`, `HUGEINT`, `REAL` | `number` |
| anything else (`VARCHAR`, etc.) | `string` |

## Choosing measures

Every cube starts with:

```yaml
- name: count
  type: count
  description: Number of <plural entity noun>.
```

Beyond `count`, curate a short list — don't mechanically add a measure for
every numeric column. Read the dbt column description to judge the right
aggregation:

- **Per-game / per-unit averages, ratings, percentages** (dbt description says
  "average", "per game", ends in "pct", or is a rate 0-1) → `avg`. Example:
  `avg_point_margin`, `avg_popularity`.
- **Totals / counts accumulated over a career or dataset** (dbt description
  says "total", "count of", "sum of") → `sum`. Example: a StatsBomb
  `total_shots` column aggregating across matches should become
  `sum_total_shots`, not `avg_total_shots` — summing career/dataset totals is
  the meaningful operation, unlike NBA's per-game columns which get averaged.
- **"Best/highest so far" style stats** where a max is meaningful on its own
  (follower counts, popularity ceilings) → also add a `max` alongside the
  `avg`, as `spotify_top_artists`/`spotify_top_tracks` do with
  `max_followers` / `max_popularity`.
- **Boolean flags worth expressing as a rate** (e.g. a win/loss flag) →
  a computed `avg` measure over a `CASE WHEN ... THEN 1.0 ELSE 0.0 END` SQL
  expression, named `<thing>_rate`. See `home_win_rate` in
  `nba_game_results`.
- **A categorical column with a small fixed set of values** (an
  `accepted_values` test in the dbt YAML is the signal) that a rate measure
  makes sense for → propose **one rate measure per value**, not just a single
  "positive" case. A match outcome column with `home_win`/`away_win`/`draw`
  should get `home_win_rate`, `away_win_rate`, *and* `draw_rate` — mirroring
  NBA's single `home_win_rate` (built for a genuinely binary
  `home_team_won`) onto a 3+ value column and stopping at one is an easy trap.
- **A "point-in-time" value bounded by a time column in the same row** — an
  opening/closing price, a first/last reading of something — is *not* an
  `avg` candidate, even though it looks numeric like one. Averaging opens and
  closes across rows produces a number that isn't the open or close of
  anything once Cube rolls the query up to a coarser time granularity than
  the mart's native grain (e.g. querying hourly candles grouped by day). Use
  `MIN_BY`/`MAX_BY` keyed on the row's time column instead, so the value stays
  correct at any granularity:
  ```yaml
  - name: open
    sql: "MIN_BY({CUBE}.open, {CUBE}.candle_open_time)"
    type: number
    description: Opening price — the open of the earliest candle in the matching time bucket.

  - name: close
    sql: "MAX_BY({CUBE}.close, {CUBE}.candle_open_time)"
    type: number
    description: Closing price — the close of the latest candle in the matching time bucket.
  ```
  By contrast, a column that's already a *range extremum over the window*
  (a candle's `high`/`low`) is correctly handled by plain `max`/`min` — those
  stay correct at any granularity without needing `_BY`. And a genuinely
  additive quantity (`volume`) is correctly a `sum`. The three read similarly
  numeric but need three different treatments — judge each column by what
  kind of quantity it actually is, not by its data type.

Measure descriptions follow a fixed phrasing pattern — match it:

- `avg`: "Average <what the number represents> across matching <entity
  plural>."
- `max`: "Highest <what> among matching <entity plural>."
- `sum`: "Total <what> across matching <entity plural>."
- `count`: "Number of <entity plural>."
- computed rate: "Share of <entity plural> in this slice where <condition>."

## File layout template

```yaml
cubes:
  - name: <mart_name>
    sql_table: marts.<mart_name>
    description: >
      <adapted dbt description — see above>

    dimensions:
      - name: <col>
        sql: <col>
        type: <string|number|boolean|time>
        primary_key: true   # only on grain column(s)
        description: <dbt column description, verbatim>

      - name: <col2>
        ...

    measures:
      - name: count
        type: count
        description: Number of <entities>.

      - name: <measure_name>
        sql: <col>            # omit for type: count
        type: <avg|sum|max|count>
        description: <phrasing per pattern above>
```

Blank line after the description block and between the last dimension and
`measures:`. No blank line needed between the individual dimension/measure
entries beyond the single line the YAML list already gives them (match the
spacing in the existing files exactly — one blank line between each
dimension/measure entry, as shown above).

## Validation

There is no `cube:validate` task — only `task cube:dev`, which starts a
long-running dev server and Playground (http://localhost:4000). It's the only
way to confirm the YAML actually compiles as a valid Cube schema. Since the
DuckDB driver always opens `data/spotify.duckdb` read-write with no read-only
option, **never** run it while `task dbt:run` or an ingest job is running.

At minimum, always check without starting the server:
1. The YAML parses (`yaml.safe_load`).
2. Every `sql:` value referenced in a dimension or measure corresponds to a
   real column reported by `introspect_mart.py` (its `warnings` list already
   flags mismatches between dbt docs and the live table — cross-check your
   own dimension/measure list against `duckdb_columns` too).

If the user wants to see the cube in Playground, offer to run `task cube:dev`
for them, with the concurrency warning above.
