"""DuckDB write helpers for the bronze layer.

Mirrors the idempotent full-replace pattern used elsewhere in the repo
(data-ingestion/nba/ingestion/load.py): each table is rebuilt from scratch on
every run, so regenerating is safe and reproducible. Every bronze table carries
an ``ingested_at`` timestamp, matching the project convention that this column is
threaded through from the raw layer.
"""
from __future__ import annotations

import duckdb
import pandas as pd


def connect(path: str) -> duckdb.DuckDBPyConnection:
    """Open the DuckDB file read-write (the generators own the write side)."""
    return duckdb.connect(path)


def replace_table(conn: duckdb.DuckDBPyConnection, schema: str, table: str, df: pd.DataFrame) -> int:
    """Full-replace ``<schema>.<table>`` with ``df`` plus an ingested_at column.

    Returns the row count written.
    """
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    conn.register("_df_tmp", df)
    conn.execute(
        f"CREATE OR REPLACE TABLE {schema}.{table} AS "
        f"SELECT *, now() AS ingested_at FROM _df_tmp"
    )
    conn.unregister("_df_tmp")
    count = conn.execute(f"SELECT count(*) FROM {schema}.{table}").fetchone()[0]
    print(f"  bronze.{schema}.{table:<24} {count:>8,} rows")
    return count
