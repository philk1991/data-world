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
import os
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
