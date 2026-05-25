# dbt Conventions

## Layer responsibilities

### Staging (`models/staging/<domain>/`)
- One model per source table — no exceptions
- Rename and cast columns only; no joins, no aggregations, no business logic
- Always reference raw tables via `{{ source('<domain>', 'raw_<entity>') }}`
- Always carry `ingested_at::timestamp as ingested_at` through from the source
- Materialise as **view** (default)

### Intermediate (`models/intermediate/`)
- Combine or reshape staged data; join across source domains; derive business measures
- Never reference raw source tables — always `{{ ref('stg_...') }}`
- Materialise as **view** unless the model is expensive (then table, documented why)
- Use sparingly — prefer moving logic into marts if it's only consumed once

### Marts (`models/marts/<domain>/`)
- Final business-ready tables consumed by dashboards or analysts
- Named for the consumer concept, not the source (`top_artists_by_period`, not `stg_artists_pivoted`)
- Always `{{ ref() }}` — never `{{ source() }}`
- Materialise as **table** for batch sources; **incremental** for append-heavy streaming sources
- If a SQL file becomes too large (over 200 lines) consider creating intermeidate models to hold reusable logic

---

## Naming conventions

| Layer | Pattern | Examples |
|---|---|---|
| Staging | `stg_<domain>__<entity>` | `stg_spotify__top_artists`, `stg_statsbomb__matches` |
| Intermediate | `int_<verb>_<noun>` | `int_enrich_tracks`, `int_aggregate_match_events` |
| Marts | `<entity>` or `<entity>_by_<dimension>` | `top_artists_by_period`, `sb_match_summary` |

> Note: existing staging models use a single-underscore pattern (`stg_top_artists`, `stg_sb_matches`). New models use the double-underscore standard above; existing models are not renamed.

**Column naming:**
- IDs: `<entity>_id`
- Names: `<entity>_name`
- Timestamps: `<event>_at` (datetime), `<event>_date` (date only)
- Metrics: `total_<thing>` or descriptive (`popularity`, `followers`)
- Pivoted ranks: `rank_<period>` (e.g. `rank_short_term`)
- Derived: descriptive of the calculation (`goal_difference`, `notional_value`)

---

## Testing standards

### Staging
- `not_null` on every column
- `unique` on the natural key for the entity (e.g. `artist_id`, `event_id`, `played_at`)
- `accepted_values` on every categorical column with a known finite value set

### Intermediate
- `not_null` and `unique` on the grain key

### Marts
- `not_null` and `unique` on the grain key
- `accepted_values` on any categorical column that consumers are likely to filter on

---

## YAML file structure

Each domain has up to three yml files:

```
staging/<domain>/
  sources_<domain>.yml     # raw source table definitions (minimal, no column-level)
  staging_<domain>.yml     # staging model columns + tests

marts/<domain>/
  marts_<domain>.yml       # mart model columns + tests
```

**sources yml** — table-level descriptions only, no column definitions:
```yaml
version: 2
sources:
  - name: raw_<domain>
    schema: raw_<domain>
    tables:
      - name: raw_<entity>
        description: <one line>
```

**staging yml** — full column definitions with descriptions and tests:
```yaml
version: 2
models:
  - name: stg_<domain>__<entity>
    description: <what this model represents>
    columns:
      - name: <column>
        description: <what it is, where it comes from, when it can be null>
        tests:
          - not_null
          - unique   # on natural keys only
```

**marts yml** — same shape as staging yml; descriptions should explain derivation logic for computed columns.

---

## dbt_project.yml materialisation

When adding a new domain, register its materialisation in `dbt_project.yml` under `models: spotify:`:

```yaml
staging:
  <domain>:
    +materialized: view
    +schema: staging_<domain>
marts:
  <domain>:
    +materialized: table   # or incremental for streaming
    +schema: marts
```
