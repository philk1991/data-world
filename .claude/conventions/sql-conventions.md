# SQL Conventions

## CTE structure

Every model follows the same three-zone structure:

1. **Import CTEs** — one per source or ref, named after the entity being imported
2. **Transform CTEs** — descriptive names that say what's happening (`pivoted`, `event_counts`, `enriched`, `aggregated`)
3. **Final output** — either `SELECT * FROM <last_transform_cte>` or an explicit select if columns need reordering/renaming

```sql
-- Import
WITH artists AS (
    SELECT *
    FROM
        {{ ref('stg_spotify__top_artists') }}
),

-- Transform
pivoted AS (
    SELECT
        ...
    FROM
        artists
    GROUP BY
        ...
)

-- Final
SELECT *
FROM
    pivoted
ORDER BY
    ...
```

Separate the import and transform zones with a blank line and a `-- Transform` comment when the model has more than two CTEs.

---

## Formatting

- **Indentation**: 4 spaces, no tabs
- **Keywords, functions, types and literals**: UPPERCASE — `SELECT`, `FROM`, `WHERE`, `LEFT JOIN`, `GROUP BY`, `CASE`, `WHEN`, `AND`, `AS`, `USING`, `WITH`, `COALESCE`, `COUNT`, `SUM`, `DATE_TRUNC`, `::TIMESTAMP`, `NULL`, `TRUE`
- **Identifiers**: lowercase snake_case — table names, column names, CTE names, aliases. Exception: NBA staging models reference the Kaggle source's camelCase columns as spelled (`hometeamName`) before renaming them
- **Commas**: trailing (end of line), not leading
- **Column lists**: one column per line
- **Aliases**: column aliases use `AS`, one space after the expression (no alignment); table aliases have no `AS` (`FROM matches m`)
- **Clause layout**: `FROM`, `JOIN`, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY` and `LIMIT` sit alone on their line, with their contents on the next line indented one level (in line with the `SELECT` columns). A join's `USING`/`ON` goes on its own line under the joined table. `FILTER (WHERE ...)` inside an aggregate stays inline
- **Jinja blocks**: SQL inside `{% if %}` is not indented further
- **Line length**: 120 characters

---

## Linting

SQLFluff enforces the formatting rules above (config in `dbt/.sqlfluff`). Run `task dbt:lint` to check and `task dbt:fix` to auto-fix; `dbt lint` itself needs the proprietary dbt distribution.

---

## Type casting

Use DuckDB/PostgreSQL `::type` syntax — not `CAST(col AS type)`:

```sql
-- correct
ingested_at::TIMESTAMP AS ingested_at
price::DOUBLE AS price

-- avoid
CAST(ingested_at AS TIMESTAMP)
```

---

## Comments

- One-line comment above the first CTE when the model's purpose isn't obvious from its name
- Inline `--` comment on non-obvious CASE expressions or derivations
- No block comments; no multi-line comment headers

```sql
-- One row per match with aggregate event counts from conditional aggregation.
WITH matches AS (
    ...
```

---

## Null handling

- Use `COALESCE(col, default)` in marts when an outer join can produce nulls in a metric column
- Document nullable columns explicitly in YAML: `"Null if not in top 50"`

```sql
COALESCE(e.total_events, 0) AS total_events,
COALESCE(e.total_shots, 0) AS total_shots
```

---

## Joins

- Use `USING (col)` when joining on identically-named keys (cleaner, avoids duplicate column)
- Use explicit short table aliases (`m`, `e`, `ec`) — initials of the CTE name
- Alias assignment goes on the `FROM` / `JOIN` line, not inline

```sql
FROM
    matches m
LEFT JOIN
    event_counts e
    USING (match_id)
```

When keys differ between tables, use `ON`:

```sql
FROM
    matches m
LEFT JOIN
    competitions c
    ON m.competition_id = c.competition_id
```

---

## Staging-specific patterns

Staging models use a single `source` CTE with a pass-through select. Keep them minimal:

```sql
-- Light cleaning: rename columns, cast types, pass ingested_at through.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_spotify', 'raw_top_artists') }}
)

SELECT
    id AS artist_id,
    name AS artist_name,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
```

No aggregations, no filters (unless removing structural duplicates from the raw layer), no joins.

---

## Mart-specific patterns

**Pivot with conditional aggregation:**
```sql
MAX(CASE WHEN time_range = 'short_term' THEN rank END) AS rank_short_term,
MAX(CASE WHEN time_range = 'medium_term' THEN rank END) AS rank_medium_term,
```

**Incremental models** — always filter on the incremental column:
```sql
{% if is_incremental() %}
WHERE
    trade_time > (
        SELECT MAX(trade_time)
        FROM
            {{ this }}
    )
{% endif %}
```
