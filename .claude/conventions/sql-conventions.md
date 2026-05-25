# SQL Conventions

## CTE structure

Every model follows the same three-zone structure:

1. **Import CTEs** — one per source or ref, named after the entity being imported
2. **Transform CTEs** — descriptive names that say what's happening (`pivoted`, `event_counts`, `enriched`, `aggregated`)
3. **Final output** — either `select * from <last_transform_cte>` or an explicit select if columns need reordering/renaming

```sql
-- Import
with artists as (
    select * from {{ ref('stg_spotify__top_artists') }}
),

-- Transform
pivoted as (
    select
        ...
    from artists
    group by ...
)

-- Final
select * from pivoted
order by ...
```

Separate the import and transform zones with a blank line and a `-- Transform` comment when the model has more than two CTEs.

---

## Formatting

- **Indentation**: 4 spaces, no tabs
- **Keywords**: UPPERCASE — `SELECT`, `FROM`, `WHERE`, `LEFT JOIN`, `INNER JOIN`, `GROUP BY`, `ORDER BY`, `HAVING`, `CASE`, `WHEN`, `THEN`, `ELSE`, `END`, `AND`, `OR`, `NOT`, `NULL`, `AS`, `ON`, `USING`, `WITH`, `COALESCE`, `COUNT`, `SUM`, `MAX`, `MIN`, `AVG`
- **Identifiers**: lowercase snake_case — table names, column names, CTE names, aliases
- **Commas**: trailing (end of line), not leading
- **Column lists**: one column per line

---

## Type casting

Use DuckDB/PostgreSQL `::type` syntax — not `CAST(col AS type)`:

```sql
-- correct
ingested_at::timestamp as ingested_at
price::double as price

-- avoid
CAST(ingested_at AS timestamp)
```

---

## Comments

- One-line comment above the first CTE when the model's purpose isn't obvious from its name
- Inline `--` comment on non-obvious CASE expressions or derivations
- No block comments; no multi-line comment headers

```sql
-- One row per match with aggregate event counts from conditional aggregation.
with matches as (
    ...
```

---

## Null handling

- Use `coalesce(col, default)` in marts when an outer join can produce nulls in a metric column
- Document nullable columns explicitly in YAML: `"Null if not in top 50"`

```sql
coalesce(e.total_events, 0) as total_events,
coalesce(e.total_shots, 0) as total_shots
```

---

## Joins

- Use `USING (col)` when joining on identically-named keys (cleaner, avoids duplicate column)
- Use explicit short table aliases (`m`, `e`, `ec`) — initials of the CTE name
- Alias assignment goes on the `FROM` / `JOIN` line, not inline

```sql
from matches m
left join event_counts e using (match_id)
```

When keys differ between tables, use `ON`:

```sql
from matches m
left join competitions c on m.competition_id = c.competition_id
```

---

## Staging-specific patterns

Staging models use a single `source` CTE with a pass-through select. Keep them minimal:

```sql
-- Light cleaning: rename columns, cast types, pass ingested_at through.
with source as (
    select * from {{ source('raw_spotify', 'raw_top_artists') }}
)

select
    id as artist_id,
    name as artist_name,
    ingested_at::timestamp as ingested_at
from source
```

No aggregations, no filters (unless removing structural duplicates from the raw layer), no joins.

---

## Mart-specific patterns

**Pivot with conditional aggregation:**
```sql
max(case when time_range = 'short_term' then rank end) as rank_short_term,
max(case when time_range = 'medium_term' then rank end) as rank_medium_term,
```

**Incremental models** — always filter on the incremental column:
```sql
{% if is_incremental() %}
where trade_time > (select max(trade_time) from {{ this }})
{% endif %}
```
