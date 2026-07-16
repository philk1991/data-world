"""Shared helpers for the Verano ML modules.

Reuses the data-generation config for the DuckDB path / seed / window so the whole
build stays on one set of dials. Each ML module opens the file read-write, reads
gold, computes, and writes one or more tables into the Python-owned `ml` schema.
"""
from __future__ import annotations

import os
import sys

import duckdb
import numpy as np
import pandas as pd

# Reuse the generator config (DUCKDB_PATH, SEED, WINDOW_*).
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data-generation"))
import config as C  # noqa: E402

DUCKDB_PATH = C.DUCKDB_PATH
SEED = C.SEED
WINDOW_START = pd.Timestamp(C.WINDOW_START)
WINDOW_END = pd.Timestamp(C.WINDOW_END)


def connect() -> duckdb.DuckDBPyConnection:
    """Open verano.duckdb read-write (ML owns the `ml` schema)."""
    return duckdb.connect(DUCKDB_PATH)


def write_ml_table(con: duckdb.DuckDBPyConnection, name: str, df: pd.DataFrame) -> int:
    """Full-replace ml.<name> with df. Returns row count."""
    con.execute("CREATE SCHEMA IF NOT EXISTS ml")
    con.register("_ml_tmp", df)
    con.execute(f"CREATE OR REPLACE TABLE ml.{name} AS SELECT * FROM _ml_tmp")
    con.unregister("_ml_tmp")
    n = con.execute(f"SELECT count(*) FROM ml.{name}").fetchone()[0]
    print(f"  wrote ml.{name}: {n:,} rows")
    return n


def minmax(s: pd.Series) -> pd.Series:
    """Scale a series to [0, 1]; constant series -> 0.5."""
    lo, hi = s.min(), s.max()
    if hi <= lo:
        return pd.Series(0.5, index=s.index)
    return (s - lo) / (hi - lo)


def rule(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")
