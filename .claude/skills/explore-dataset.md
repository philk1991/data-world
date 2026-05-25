---
name: explore-dataset
description: Profile a raw DuckDB dataset before building dbt models. Outputs a structured EDA markdown report (column stats, missing data, top values, suggested models, relation to existing dbt) printed to the terminal and saved to .claude/eda/. Argument is a domain name (spotify, crypto, statsbomb) or a specific table name.
---

# explore-dataset

Profile one or more raw DuckDB tables before building dbt models. Produces a structured EDA report — printed to the terminal and written to `.claude/eda/`.

## Step 1 — Parse the argument and discover tables

| Input | Behaviour |
|---|---|
| `spotify` | All tables in schemas whose name contains "spotify" |
| `crypto` | All tables in schemas whose name contains "crypto" |
| `statsbomb` | All tables in schemas whose name contains "statsbomb" |
| `raw_top_artists` | That specific table, searched across all schemas |
| `raw_spotify.raw_top_artists` | That exact schema.table |

Run this discovery script to resolve the argument to a list of matching tables. Replace `ARG_VALUE` with the actual argument.

    source .venv/bin/activate && python3 - <<'PYEOF'
    import duckdb, json

    arg = 'ARG_VALUE'

    conn = duckdb.connect('data/spotify.duckdb', read_only=True)
    try:
        conn.execute("ATTACH 'data/crypto_raw.duckdb' AS crypto_raw (READ_ONLY)")
    except Exception:
        pass

    main_db = conn.execute('SELECT current_database()').fetchone()[0]
    rows = conn.execute("""
        SELECT database_name, schema_name, table_name
        FROM duckdb_tables()
        ORDER BY database_name, schema_name, table_name
    """).fetchall()

    arg_lower = arg.lower().strip()
    if '.' in arg_lower:
        s, t = arg_lower.split('.', 1)
        targets = [(db, sc, tb) for db, sc, tb in rows if sc.lower() == s and tb.lower() == t]
    elif any(tb.lower() == arg_lower for _, _, tb in rows):
        targets = [(db, sc, tb) for db, sc, tb in rows if tb.lower() == arg_lower]
    else:
        targets = [(db, sc, tb) for db, sc, tb in rows
                   if arg_lower in sc.lower() or arg_lower in tb.lower()]

    if not targets:
        print(json.dumps({'error': f'No tables found matching: {arg}',
                          'available': [f'{sc}.{tb}' for _, sc, tb in rows]}))
    else:
        print(json.dumps([
            {'database': db, 'schema': sc, 'table': tb,
             'ref': f'"{sc}"."{tb}"' if db == main_db else f'"{db}"."{sc}"."{tb}"'}
            for db, sc, tb in targets
        ]))
    PYEOF

Stop if the script reports an error (e.g. DB locked). Otherwise collect the list of targets.

## Step 2 — Decide profiling strategy

**Choose sequential or parallel based on the number of tables matched:**

| Tables matched | Approach | Reason |
|---|---|---|
| 1–2 | Sequential script (Step 3) | Spawn overhead (~2s per agent) costs more than it saves |
| 3+ | Parallel sub-agents | SUMMARIZE on a large table takes 3–5s. Running 4 tables sequentially means 12–20s of waiting. Parallel agents collapse this to the slowest single table — typically 3–5s regardless of how many tables there are |

---

### If 3+ tables — spawn profiling sub-agents in parallel

Spawn one **general-purpose** sub-agent per table **in a single message**.
Sending all spawns in one message is what makes them run concurrently — spawning them
one at a time would make execution sequential again.

Give each sub-agent this prompt, substituting the table details:

> Connect to DuckDB: `duckdb.connect('data/spotify.duckdb', read_only=True)`.
> Also try: `conn.execute("ATTACH 'data/crypto_raw.duckdb' AS crypto_raw (READ_ONLY)")`.
>
> Profile this table: `<ref>` (e.g. `"raw_spotify"."raw_top_artists"`)
>
> Run these queries:
> 1. `SELECT COUNT(*) FROM <ref>` — row count
> 2. `SUMMARIZE <ref>` — full column statistics
> 3. For each column where column_type is not numeric and not temporal, and approx_unique ≤ 50:
>    `SELECT col::VARCHAR AS value, COUNT(*) AS cnt FROM <ref> GROUP BY 1 ORDER BY cnt DESC LIMIT 15`
>
> Return a single JSON object with this exact shape:
> ```json
> {
>   "schema": "raw_spotify",
>   "table": "raw_top_artists",
>   "row_count": 150,
>   "col_count": 8,
>   "columns": [
>     {
>       "name": "artist_id", "type": "VARCHAR",
>       "null_count": 0, "null_pct": 0.0, "approx_unique": 50,
>       "min": null, "max": null, "avg": null,
>       "q25": null, "q50": null, "q75": null,
>       "is_numeric": false, "is_temporal": false,
>       "top_values": [{"value": "abc123", "count": 3}]
>     }
>   ]
> }
> ```
> Return ONLY the JSON. No explanation.

Collect all sub-agent JSON results. Merge into an array. Skip to Step 4.

---

### If 1–2 tables — sequential script (Step 3)

Continue to Step 3.

## Step 3 — Profile sequentially (1–2 tables only)

Run this script. Replace `ARG_VALUE` with the actual argument.

    source .venv/bin/activate && python3 - <<'PYEOF'
    import duckdb, json

    arg = 'ARG_VALUE'

    conn = duckdb.connect('data/spotify.duckdb', read_only=True)
    try:
        conn.execute("ATTACH 'data/crypto_raw.duckdb' AS crypto_raw (READ_ONLY)")
    except Exception:
        pass

    main_db = conn.execute('SELECT current_database()').fetchone()[0]
    rows = conn.execute("""
        SELECT database_name, schema_name, table_name
        FROM duckdb_tables()
        ORDER BY database_name, schema_name, table_name
    """).fetchall()

    arg_lower = arg.lower().strip()
    if '.' in arg_lower:
        s, t = arg_lower.split('.', 1)
        targets = [(db, sc, tb) for db, sc, tb in rows if sc.lower() == s and tb.lower() == t]
    elif any(tb.lower() == arg_lower for _, _, tb in rows):
        targets = [(db, sc, tb) for db, sc, tb in rows if tb.lower() == arg_lower]
    else:
        targets = [(db, sc, tb) for db, sc, tb in rows
                   if arg_lower in sc.lower() or arg_lower in tb.lower()]

    def ref(db, schema, table):
        if db == main_db:
            return f'"{schema}"."{table}"'
        return f'"{db}"."{schema}"."{table}"'

    results = []
    for db, schema, table in targets:
        tref = ref(db, schema, table)
        row_count = conn.execute(f'SELECT COUNT(*) FROM {tref}').fetchone()[0]
        summary = conn.execute(f'SUMMARIZE {tref}').fetchdf()

        columns = []
        for _, r in summary.iterrows():
            ctype = str(r['column_type']).upper()
            is_numeric = any(t in ctype for t in [
                'INT', 'FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC',
                'HUGEINT', 'REAL', 'TINYINT', 'SMALLINT', 'BIGINT'
            ])
            is_temporal = any(t in ctype for t in ['TIMESTAMP', 'DATE', 'TIME', 'INTERVAL'])
            null_pct = float(r['null_percentage']) if r['null_percentage'] is not None else 0.0
            approx_unique = int(r['approx_unique']) if r['approx_unique'] is not None else None

            col = {
                'name': r['column_name'],
                'type': r['column_type'],
                'null_count': int(round(null_pct / 100 * row_count)) if row_count else 0,
                'null_pct': round(null_pct, 1),
                'approx_unique': approx_unique,
                'min': str(r['min']) if r['min'] is not None else None,
                'max': str(r['max']) if r['max'] is not None else None,
                'avg': str(r['avg']) if r['avg'] is not None else None,
                'q25': str(r['q25']) if r['q25'] is not None else None,
                'q50': str(r['q50']) if r['q50'] is not None else None,
                'q75': str(r['q75']) if r['q75'] is not None else None,
                'is_numeric': is_numeric,
                'is_temporal': is_temporal,
            }

            if not is_numeric and not is_temporal and approx_unique is not None and approx_unique <= 50:
                try:
                    top = conn.execute(f"""
                        SELECT "{r['column_name']}"::VARCHAR AS value, COUNT(*) AS cnt
                        FROM {tref}
                        GROUP BY 1 ORDER BY cnt DESC LIMIT 15
                    """).fetchall()
                    col['top_values'] = [{'value': str(v), 'count': int(c)} for v, c in top]
                except Exception:
                    col['top_values'] = []

            columns.append(col)

        results.append({
            'schema': schema,
            'table': table,
            'row_count': row_count,
            'col_count': len(columns),
            'columns': columns,
        })

    print(json.dumps(results, indent=2, default=str))
    PYEOF

## Step 4 — Read manifest for existing dbt context

    source .venv/bin/activate && python3 - <<'PYEOF'
    import json

    arg = 'ARG_VALUE'
    arg_lower = arg.lower()

    try:
        with open('dbt/target/manifest.json') as f:
            manifest = json.load(f)
    except FileNotFoundError:
        print(json.dumps({'error': 'manifest.json not found — run dbt parse or dbt compile first'}))
        raise SystemExit(0)

    sources = [
        {'name': v['name'], 'schema': v['schema'], 'source_name': v['source_name']}
        for v in manifest.get('sources', {}).values()
        if arg_lower in v.get('schema', '').lower()
        or arg_lower in v.get('name', '').lower()
        or arg_lower in v.get('source_name', '').lower()
    ]

    models = [
        {
            'name': v['name'],
            'schema': v['schema'],
            'path': v['original_file_path'],
            'description': v.get('description', ''),
            'meta': v.get('meta', {}),
        }
        for v in manifest.get('nodes', {}).values()
        if v.get('resource_type') == 'model'
        and arg_lower in v.get('name', '').lower()
    ]

    all_models = [
        {'name': v['name'], 'schema': v['schema'], 'description': v.get('description', '')}
        for v in manifest.get('nodes', {}).values()
        if v.get('resource_type') == 'model'
    ]

    print(json.dumps({
        'matched_sources': sources,
        'matched_models': models,
        'all_models': all_models,
    }, indent=2))
    PYEOF

## Step 5 — Assemble and output the markdown report

Using the profiling output from Steps 2–3 and the manifest context from Step 4, assemble the full report following the structure below. Then:

1. Print the full report to the terminal
2. Write it to `.claude/eda/<ARG_VALUE>_<YYYYMMDD>.md` using the Write tool (create the directory if needed)

---

## Report structure

    # Dataset Exploration: `<ARG>`
    **Generated:** <YYYY-MM-DD HH:MM>
    **Tables analysed:** N  |  **Total rows:** N

    ---

    ## Table: `<schema>.<table>`
    **Rows:** N  |  **Columns:** N

    ### Column Profile

    | Column | Type | Non-null | Null % | Distinct |
    |---|---|---|---|---|

    For numeric columns, add a stats sub-table immediately after the main profile:

    | Column | Min | Q25 | Median | Q75 | Max | Avg |
    |---|---|---|---|---|---|---|

    For low-cardinality categorical columns (distinct ≤ 50), add a top-values table:

    ### Top Values — `<column>` (N distinct)
    | Value | Count |
    |---|---|

    For temporal columns, add a date range note:
    > Range: `<min>` → `<max>`

    ---

    Repeat the table section for each table analysed.

    ---

    ## Missing Data
    Only include columns where null_pct > 0, sorted by null_pct descending.

    | Table | Column | Null count | Null % |
    |---|---|---|---|

    If no nulls exist across all tables: `✅ No missing data found.`

    ---

    ## Suggested dbt Models

    ### Staging
    For each raw table, suggest a staging model following `stg_<domain>__<entity>`.
    If a staging model already exists for this table (from Step 4), mark it as `(already exists)`.

    - `stg_<domain>__<entity>` — <one-line description>

    ### Potential marts
    Suggest 1–3 mart models genuinely supported by the data profiled.
    Name each model, describe the grain, and state the business question it answers.

    ---

    ## Relation to Existing dbt

    ### Already modelled in this domain
    List any models from Step 4 already built for this domain.
    If none: `No models yet — this is a new domain.`

    ### Potential joins and enrichments
    Review `all_models` from Step 4. Identify models from other domains that share
    a likely join key with this dataset. Name the join key and explain what analysis it enables.
