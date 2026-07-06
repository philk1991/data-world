---
name: test-failures
description: Run dbt tests, diagnose failures by querying the affected tables, and output a markdown report with suggested fixes. Optional argument narrows the scope (e.g. "marts for spotify", "staging", "crypto").
---

# test-failures

Run dbt tests, diagnose each failure with a live diagnostic query, and print a structured markdown report with actionable suggested fixes.

## Step 1 — Parse the argument

If the user provided an argument, translate it to a dbt node selector:

| Argument | Selector |
|---|---|
| "marts for spotify" | `marts.spotify` |
| "staging for statsbomb" | `staging.statsbomb` |
| "spotify" | `staging.spotify marts.spotify` |
| "crypto" | `staging.crypto marts.crypto` |
| "statsbomb" | `staging.statsbomb marts.statsbomb` |
| "staging" | `staging` |
| "marts" | `marts` |
| (no argument) | (omit `--select`) |

For multi-part selectors (two paths), pass them space-separated as multiple `--select` values or combine into one `dbt test` call.

## Step 2 — Run dbt test

Run from the project root. If the DB is locked by another process, report that clearly and stop.

    bash -c "source .venv/bin/activate && cd dbt && dbt test [--select <selector>] 2>&1"

dbt exits non-zero when tests fail — that is expected. Continue regardless.

## Step 3 — Parse results from JSON

Read both files with Python:

    python3 - <<'EOF'
    import json, sys

    with open('dbt/target/run_results.json') as f:
        run_results = json.load(f)
    with open('dbt/target/manifest.json') as f:
        manifest = json.load(f)

    failures = [
        r for r in run_results['results']
        if r['unique_id'].startswith('test.') and r['status'] in ('fail', 'error')
    ]

    for r in failures:
        uid = r['unique_id']
        node = manifest['nodes'].get(uid, {})
        tm = node.get('test_metadata', {})
        attached = node.get('attached_node', '')
        model_node = manifest['nodes'].get(attached, {})
        print(json.dumps({
            'uid': uid,
            'status': r['status'],
            'failures': r['failures'],
            'test_type': tm.get('name'),
            'column': tm.get('kwargs', {}).get('column_name'),
            'kwargs': tm.get('kwargs', {}),
            'model_name': model_node.get('name'),
            'schema': model_node.get('schema'),
            'fqn': node.get('fqn', []),
            'compiled_code': r.get('compiled_code', ''),
        }))
    EOF

Each line of output is a JSON object for one failure. Collect them all.

## Step 4 — Diagnose failures

**Decide whether to use sub-agents or a sequential script based on failure count:**

| Failures | Approach | Reason |
|---|---|---|
| < 3 | Sequential Python script | Sub-agent spawn overhead (~2s each) costs more than it saves at low counts |
| ≥ 3 | Parallel sub-agents | Each diagnosis is fully independent — no shared state, no ordering dependency. Wall-clock time drops from N × query_time to max(query_time) |

---

### If ≥ 3 failures — spawn sub-agents in parallel

Spawn one **general-purpose** sub-agent per failure **in a single message** — not one at a time.
Waiting for each to finish before spawning the next would make it sequential again, defeating
the point. All agents start simultaneously and their results are collected when the last one finishes.

Give each sub-agent this prompt, substituting the failure JSON:

> Connect to DuckDB: `duckdb.connect('data/spotify.duckdb', read_only=True)`.
> Also try: `conn.execute("ATTACH 'data/crypto_raw.duckdb' AS crypto_raw (READ_ONLY)")`.
>
> Run a diagnostic query for this dbt test failure and return two things:
> 1. A markdown table of the query results
> 2. A specific suggested fix (one short paragraph) based on what the data shows
>
> Failure JSON: `<paste the JSON object from Step 3>`
>
> Query logic by test type:
> - **not_null**: `SELECT COUNT(*) AS null_count FROM "schema"."model" WHERE "col" IS NULL`
> - **unique**: `SELECT "col", COUNT(*) AS occurrences FROM "schema"."model" GROUP BY "col" HAVING COUNT(*) > 1 ORDER BY occurrences DESC LIMIT 10`
> - **accepted_values**: `SELECT "col", COUNT(*) AS row_count FROM "schema"."model" WHERE "col" NOT IN ('val1','val2',...) GROUP BY "col" ORDER BY row_count DESC`
> - **other**: `SELECT * FROM (<compiled_code>) _failures LIMIT 10`
>
> Return ONLY the markdown table and the suggested fix. No preamble, no explanation of what you did.

Collect all sub-agent results. Proceed to Step 5.

---

### If < 3 failures — sequential script

For each failure, run:

    python3 - <<'EOF'
    import duckdb, json, sys

    conn = duckdb.connect('data/spotify.duckdb', read_only=True)
    try:
        conn.execute("ATTACH 'data/crypto_raw.duckdb' AS crypto_raw (READ_ONLY)")
    except Exception:
        pass  # crypto DB may not exist or may be locked

    failure = json.loads(sys.argv[1])  # pass the JSON from Step 3
    schema = failure['schema']
    model = failure['model_name']
    col = failure['column']
    test_type = failure['test_type']

    if test_type == 'not_null':
        sql = f'SELECT COUNT(*) AS null_count FROM "{schema}"."{model}" WHERE "{col}" IS NULL'
    elif test_type == 'unique':
        sql = f'''
            SELECT "{col}", COUNT(*) AS occurrences
            FROM "{schema}"."{model}"
            GROUP BY "{col}"
            HAVING COUNT(*) > 1
            ORDER BY occurrences DESC
            LIMIT 10
        '''
    elif test_type == 'accepted_values':
        values = failure['kwargs'].get('values', [])
        vals_sql = ', '.join(f"'{v}'" for v in values)
        sql = f'''
            SELECT "{col}", COUNT(*) AS row_count
            FROM "{schema}"."{model}"
            WHERE "{col}" NOT IN ({vals_sql})
            GROUP BY "{col}"
            ORDER BY row_count DESC
        '''
    else:
        base = failure['compiled_code'].strip().rstrip(';')
        sql = f'SELECT * FROM ({base}) _failures LIMIT 10'

    try:
        result = conn.execute(sql).fetchdf()
        print(result.to_markdown(index=False))
    except Exception as e:
        print(f'Could not run diagnostic query: {e}')
    EOF

## Step 5 — Output the markdown report

After gathering all diagnostics, print the full report to the terminal using this structure.
Output this as plain text — it will render as markdown in the terminal.

---

    # dbt Test Failure Report

    **Selector:** <selector or "full project">
    **Timestamp:** <datetime of run_results.json invocation_command>
    **Summary:** X failure(s) | Y test(s) passed

    ---

    ## 1. `<test_type>` — `<schema>.<model>.<column>`

    **Model:** `<schema>.<model>`
    **Column:** `<column>`
    **Test:** `<test_type>`
    **Failing rows:** <N>

    ### Diagnosis

    <table from diagnostic query>

    ### Suggested fix

    <specific fix based on test type and diagnostic findings — see guidance below>

    ---

    ## Summary table

    | # | Model | Column | Test | Failing rows |
    |---|---|---|---|---|
    | 1 | ... | ... | ... | ... |

---

If there are no failures:

    # dbt Test Report

    **Selector:** <selector>
    ✅ All N tests passed.

## Suggested fix guidance

Write a specific fix, not a generic one. Use the diagnostic data to explain exactly what went wrong.

**not_null** — N nulls found in `<column>`. Check whether the upstream source can contain nulls
for this field. If nulls are valid, remove the `not_null` test or add a `coalesce` in the model SQL.
If they're unexpected, check the ingestion script or staging model for the missing cast/filter.

**unique** — show which values are duplicated and how many times. Check whether the model's grain
is correct. If a pivot or GROUP BY is missing a column, show the exact change needed to the SQL.

**accepted_values** — show which unexpected values appeared. Either the allowed values list in the
YAML needs updating (if the new value is valid), or the upstream data has a bug that needs fixing
in the ingestion script or staging model.

**relationship / generic** — show sample failing rows from the compiled SQL. Explain what the
rows represent and why they shouldn't exist per the test definition.
