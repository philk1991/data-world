# Ingestion conventions

The rules every batch API pipeline in this project follows. They exist so dbt,
Dagster, and the dashboards can treat every raw source identically. Deviating
breaks that uniformity, so follow them unless the user explicitly overrides.

## Naming

| Thing | Rule | Example (`source = jsonplaceholder`) |
|---|---|---|
| Package dir | `data-ingestion/<source>/` | `data-ingestion/jsonplaceholder/` |
| Entity module | `<source>/ingestion/<entity>.py` | `jsonplaceholder/ingestion/posts.py` |
| Entry point | `data-ingestion/ingest_<source>.py` | `ingest_jsonplaceholder.py` |
| Schema | `raw_<source>` | `raw_jsonplaceholder` |
| Table | `raw_<source>_<entity>` | `raw_jsonplaceholder_posts` |
| Fetch fn | `fetch_<entity>() -> list[dict]` | `fetch_posts()` |
| Load fn | `load_<entity>(conn, records)` | `load_posts(conn, posts)` |
| Task | `ingest:<source>` | `task ingest:jsonplaceholder` |
| Auth env var | `<SOURCE>_API_KEY` (uppercase) | `JSONPLACEHOLDER_API_KEY` |

`<entity>` is singular-or-plural to match the resource as the API names it
(`posts`, `users`, `pokemon`). Table names use the same token.

> Note the schema/table doubling: `raw_<source>.raw_<source>_<entity>`. It looks
> redundant but matches StatsBomb (`raw_statsbomb.raw_sb_*`) and NBA
> (`raw_nba.raw_nba_*`) — the schema scopes the source, the table prefix keeps
> names unambiguous when queried unqualified.

## Every row gets `ingested_at`

Compute one UTC timestamp per `fetch_` call and stamp it on every record:

```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc).isoformat()
```

The column is `ingested_at TIMESTAMPTZ`, always last in the table.

## DuckDB path

The entry point resolves the database path the same way every existing pipeline
does — env override, else the shared default. Batch sources share
`data/spotify.duckdb` (each isolated in its own `raw_<source>` schema); only
streaming sources get a dedicated file.

```python
_DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "spotify.duckdb")
db_path = os.environ.get("DUCKDB_PATH", _DEFAULT_DB_PATH)
os.makedirs(os.path.dirname(db_path), exist_ok=True)
```

Respecting `DUCKDB_PATH` is what lets the smoke test in SKILL.md Step 6 run
against a throwaway file.

## .env loading

The entry point loads the project-root `.env` (one level up from
`data-ingestion/`):

```python
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
```

Secrets are read from the environment (`os.environ.get`), never hardcoded. Add a
documented placeholder to `.env.example`.

## Type mapping (JSON → DuckDB)

| JSON value | DuckDB column type | Coercion helper |
|---|---|---|
| string | `VARCHAR` | `_str_or_none` |
| integer | `INTEGER` (use `BIGINT` if values exceed ~2.1B, e.g. snowflake IDs) | `_int_or_none` |
| float / number | `DOUBLE` | `_float_or_none` |
| boolean | `BOOLEAN` | `_bool_or_none` |
| ISO-8601 datetime string | keep as `VARCHAR` in raw | `_str_or_none` |
| null | infer the type from a non-null sample in the probe | — |
| nested object | flatten the field(s) you want to scalar columns, else drop | per field |
| array | drop in raw, or join to a string if trivial; arrays of objects belong in their own entity | — |

Keep raw faithful and flat: store what the API returns, lightly typed. Parsing
ISO strings into real timestamps, splitting arrays, and reshaping nested
structures are dbt staging concerns, not ingestion concerns. The one
transformation ingestion always does is add `ingested_at`.

## Idempotency — re-running must be safe

Every pipeline can be re-run without erroring or duplicating. Two strategies:

### Load strategy

**Full-replace** — the default. Use when the entity re-pulls comfortably in one
run (reference data, small/medium collections, full snapshots). Clear the table,
then insert everything.

```python
conn.execute("DELETE FROM raw_<source>.raw_<source>_<entity>")
# ... then executemany INSERT
```

(`CREATE OR REPLACE TABLE ... AS SELECT` is the equivalent shortcut when loading
straight from a file or a DuckDB-native reader, as `nba/ingestion/load.py` does.)

**Incremental** — use when the dataset is large, append-only, and keyed (events
per match, rows per id) so re-pulling everything each run is wasteful. Track
which keys are already loaded, skip them, and delete-before-reinsert per key so
a retry after partial failure is clean:

```python
def get_loaded_ids(conn) -> set:
    try:
        rows = conn.execute(
            "SELECT DISTINCT <key> FROM raw_<source>.raw_<source>_<entity>"
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()   # table doesn't exist yet → nothing loaded

# in load_, before inserting one key's rows:
conn.execute("DELETE FROM raw_<source>.raw_<source>_<entity> WHERE <key> = ?", [key])
```

The entry point queries `get_loaded_ids` once, then skips keys already present —
see `ingest_statsbomb.py` for the canonical shape.

## Rate limiting

Wrap network calls in retry-with-backoff on HTTP 429 (`_fetch_with_retry` in the
templates). Real APIs throttle; a multi-page or per-key loop will hit it.

## Schema creation lives in `load_`, not a migration

Each `load_` runs `CREATE SCHEMA IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS`
itself. There is no separate migration step — the table's typed DDL is
co-located with the code that writes it, so the module is self-contained.
