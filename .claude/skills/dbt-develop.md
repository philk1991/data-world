---
name: dbt-develop
description: Scaffold a new dbt model (SQL + YAML) following project conventions. Use when adding a staging, intermediate, or mart model.
---

# dbt-develop

Scaffold a new dbt model with correct SQL structure and YAML schema entry, following this project's conventions.

## Step 1 — Load conventions

Before doing anything else, read both conventions files:
- `.claude/conventions/dbt-conventions.md`
- `.claude/conventions/sql-conventions.md`

These define the authoritative standards for everything you generate.

## Step 2 — Gather intent

If the user provided a model name as an argument, use it. Otherwise ask for:

1. **Model name** — infer the layer from the prefix:
   - `stg_` prefix → staging layer
   - `int_` prefix → intermediate layer
   - anything else → mart layer

2. **Source domain** (staging only) — which domain does this model belong to?
   - Existing: `spotify`, `statsbomb`, `crypto`
   - If a new domain: you'll need to create the directory and source yml

3. **Description** — one sentence describing what the model represents

4. **Columns** — ask the user for the key columns and their types/purpose. They can be rough; you'll structure them into proper YAML.

## Step 3 — Determine file paths

| Layer | SQL path | YAML path |
|---|---|---|
| Staging | `dbt/models/staging/<domain>/stg_<domain>__<entity>.sql` | `dbt/models/staging/<domain>/staging_<domain>.yml` |
| Intermediate | `dbt/models/intermediate/int_<verb>_<noun>.sql` | `dbt/models/intermediate/intermediate.yml` |
| Mart | `dbt/models/marts/<domain>/<model_name>.sql` | `dbt/models/marts/<domain>/marts_<domain>.yml` |

For a **new domain** (staging), also create:
- `dbt/models/staging/<domain>/sources_<domain>.yml`

Check whether the target directory and YAML file already exist before writing.

## Step 4 — Generate SQL

Follow `sql-conventions.md` exactly for formatting. Use the correct template for the layer:

**Staging:**
```sql
-- <brief description if non-obvious>
with source as (
    select * from {{ source('raw_<domain>', 'raw_<entity>') }}
)

select
    <renamed_columns_with_type_casts>
from source
```

**Intermediate:**
```sql
-- <description of what this joins or derives>
with <entity_a> as (
    select * from {{ ref('stg_<domain>__<entity_a>') }}
),

<entity_b> as (
    select * from {{ ref('stg_<domain>__<entity_b>') }}
),

<transform_cte_name> as (
    select
        ...
    from <entity_a>
    <join type> join <entity_b> using (<key>)
)

select * from <transform_cte_name>
```

**Mart:**
```sql
-- <description if non-obvious>
with <entity> as (
    select * from {{ ref('stg_<domain>__<entity>') }}
),

<transform_cte_name> as (
    select
        ...
    from <entity>
)

select * from <transform_cte_name>
order by ...
```

For **incremental marts**, add the incremental filter block inside the transform CTE:
```sql
{% if is_incremental() %}
where <timestamp_col> > (select max(<timestamp_col>) from {{ this }})
{% endif %}
```

## Step 5 — Generate YAML

**If the YAML file already exists:** read it first, then append the new model entry.

**If it doesn't exist:** create a new file with `version: 2` and the `models:` array.

For **staging**, apply these tests per column:
- `not_null` on every column
- `unique` on the natural key
- `accepted_values` on any categorical column with a known finite value set

For **intermediate / marts**, apply:
- `not_null` + `unique` on the grain key
- `accepted_values` on filterable categoricals

For a **new domain** (staging), also create `sources_<domain>.yml`:
```yaml
version: 2

sources:
  - name: raw_<domain>
    schema: raw_<domain>
    tables:
      - name: raw_<entity>
        description: <one line description>
```

## Step 6 — Update dbt_project.yml (new domains only)

If this is the first model for a new source domain, add materialisation config to `dbt/dbt_project.yml` under the appropriate layer in `models: spotify:`.

## Step 7 — Validate

Run:
```
task dbt:compile
```

Surface any errors to the user and fix them before finishing. A successful compile confirms the SQL is valid and all refs/sources resolve.
