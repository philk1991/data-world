"""
Load a downloaded NBA file (CSV or Parquet) into a raw_nba.* table in DuckDB.

Uses DuckDB's native readers for a single full-replace load per file — no
row-by-row inserts. Re-running rebuilds the table from the latest snapshot, so
ingestion is idempotent. For CSVs, sample_size=-1 scans the whole file when
inferring column types, which matters for columns that are sparse across the
long history (1947–present). Parquet carries its own types and is read as-is.
"""
import duckdb

from lake import in_transaction


@in_transaction
def load_file(conn: duckdb.DuckDBPyConnection, path: str, table: str) -> None:
    """Replace raw_nba.<table> with the contents of path, adding ingested_at."""
    reader = "read_parquet(?)" if path.endswith(".parquet") else "read_csv_auto(?, sample_size=-1)"
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_nba")
    conn.execute(f"""
        CREATE OR REPLACE TABLE raw_nba.{table} AS
        SELECT *, now() AS ingested_at
        FROM {reader}
    """, [path])

    count = conn.execute(f"SELECT count(*) FROM raw_nba.{table}").fetchone()[0]
    print(f"  Loaded {count:,} rows into raw_nba.{table}")
