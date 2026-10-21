"""
DuckLake connection helper — the one place the lake's ATTACH is defined.

The batch platform's data lives in a DuckLake: Parquet files on local disk plus
a catalog in a local Postgres database. Unlike a single .duckdb file, the
catalog locks per commit rather than per connection, so ingest scripts, dbt and
readers (Cube, nao, dashboards) can all be connected at once.

`connect_lake()` returns an in-memory DuckDB connection with the lake attached
as `lake` and selected via `USE lake`, so unqualified names like
`raw_nba.raw_nba_games` or `marts.nba_team_dim` resolve inside the lake and the
existing load_* modules work unchanged.

Configuration (via .env at the project root or environment variables):
  LAKE_CATALOG   — DuckLake catalog connection, without the `ducklake:` prefix.
                   Defaults to the local Homebrew Postgres database created by
                   `task lake:init`: postgres:dbname=data_world_lake host=localhost
  LAKE_DATA_PATH — directory holding the lake's Parquet files. Defaults to
                   <project root>/data/lake/. Must be an absolute path if set.

Requires Postgres to be running: `brew services start postgresql@17`.
"""
import functools
import os
from contextlib import contextmanager
from pathlib import Path
import duckdb

LAKE_ALIAS = "lake"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CATALOG = "postgres:dbname=data_world_lake host=localhost"
_DEFAULT_DATA_PATH = str(_PROJECT_ROOT / "data" / "lake") + "/"


def lake_settings() -> tuple[str, str]:
    """Return (catalog, data_path) from the environment, falling back to defaults."""
    catalog = os.environ.get("LAKE_CATALOG", _DEFAULT_CATALOG)
    # DuckLake records the data path when the catalog is created and rejects any
    # other spelling of it (e.g. a relative or `..` path), so always normalise.
    data_path = os.path.normpath(os.path.abspath(os.environ.get("LAKE_DATA_PATH", _DEFAULT_DATA_PATH))) + "/"
    return catalog, data_path


def connect_lake(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection with the lake attached and selected.

    Pass read_only=True for consumers that should never write (the attach then
    refuses any write statement).
    """
    catalog, data_path = lake_settings()
    conn = duckdb.connect()
    conn.execute("INSTALL ducklake; LOAD ducklake; INSTALL postgres; LOAD postgres;")
    # Concurrent writers make commits race; DuckLake retries a commit that loses. The
    # default (10 retries, ~11s) gives up under load, so allow ~1 min. Kept in step
    # with the settings in dbt/profiles.yml.
    conn.execute(
        "SET ducklake_max_retry_count = 50; SET ducklake_retry_wait_ms = 50; "
        "SET ducklake_retry_backoff = 1.1;"
    )
    options = f"DATA_PATH '{data_path}'" + (", READ_ONLY" if read_only else "")
    try:
        conn.execute(f"ATTACH 'ducklake:{catalog}' AS {LAKE_ALIAS} ({options})")
    except duckdb.Error as e:
        conn.close()
        raise RuntimeError(
            f"Could not attach the DuckLake catalog '{catalog}'. Is Postgres running "
            "(`brew services start postgresql@17`) and has `task lake:init` been run?"
        ) from e
    conn.execute(f"USE {LAKE_ALIAS}")
    return conn


@contextmanager
def transaction(conn: duckdb.DuckDBPyConnection):
    """Run the block as a single commit, rolling back on error.

    Every DuckLake commit is a Postgres transaction plus a new snapshot, so
    autocommitted row-by-row writes (e.g. executemany) are slow, bloat the
    catalog with snapshots, and starve concurrent writers such as dbt. Grouping
    a load into one commit also makes its DELETE + INSERT atomic.
    """
    conn.begin()
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()


def in_transaction(load_fn):
    """Decorator for loaders shaped `load_x(conn, ...)`: run the whole load as one commit."""
    @functools.wraps(load_fn)
    def wrapper(conn, *args, **kwargs):
        with transaction(conn):
            return load_fn(conn, *args, **kwargs)
    return wrapper



def _lake_stats(conn: duckdb.DuckDBPyConnection) -> dict:
    """Snapshot count, live data/delete files, and bytes on disk (live + awaiting cleanup)."""
    _, data_path = lake_settings()
    snapshots = conn.execute(f"SELECT count(*) FROM {LAKE_ALIAS}.snapshots()").fetchone()[0]
    live_files = conn.execute(
        f"SELECT coalesce(sum(file_count + delete_file_count), 0) FROM ducklake_table_info('{LAKE_ALIAS}')"
    ).fetchone()[0]
    disk_bytes = sum(f.stat().st_size for f in Path(data_path).rglob("*") if f.is_file())
    return {"snapshots": snapshots, "live_files": live_files, "disk_mb": round(disk_bytes / 1e6, 1)}


def maintain_lake(conn: duckdb.DuckDBPyConnection, retain: str = "7 days") -> dict:
    """Compact the lake and drop history older than `retain`; return before/after stats.

    Every commit adds a snapshot and usually a small Parquet file, so without this
    the catalog and data/lake/ only ever grow. Steps, in order:
      1. flush inlined data   — small writes kept in the catalog become Parquet files
      2. merge adjacent files — combine many small files into fewer larger ones
      3. rewrite data files   — fold delete files back into their data files
      4. expire snapshots     — forget history older than `retain` (no time travel past it)
      5. cleanup old files    — delete files no remaining snapshot references
      6. delete orphaned files — remove files no commit ever recorded (e.g. a crashed
         writer's), only when over a day old so an in-flight commit's files are safe

    Safe to run alongside writers: steps 1–3 are ordinary commits (retried on conflict).
    """
    before = _lake_stats(conn)
    lake = f"'{LAKE_ALIAS}'"
    conn.execute(f"CALL ducklake_flush_inlined_data({lake})")
    conn.execute(f"CALL ducklake_merge_adjacent_files({lake})")
    conn.execute(f"CALL ducklake_rewrite_data_files({lake})")
    conn.execute(f"CALL ducklake_expire_snapshots({lake}, older_than => now() - INTERVAL '{retain}')")
    conn.execute(f"CALL ducklake_cleanup_old_files({lake}, cleanup_all => true)")
    conn.execute(f"CALL ducklake_delete_orphaned_files({lake}, older_than => now() - INTERVAL '1 day')")
    return {"before": before, "after": _lake_stats(conn)}
