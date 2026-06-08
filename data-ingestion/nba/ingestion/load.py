"""
Load a downloaded NBA CSV into a raw_nba.* table in DuckDB.

Uses DuckDB's native read_csv_auto for a single full-replace load per file —
no row-by-row inserts. Re-running rebuilds the table from the latest snapshot,
so ingestion is idempotent. sample_size=-1 scans the whole file when inferring
column types, which matters for columns that are sparse across the long history
(1947–present).
"""
import duckdb


def load_csv(conn: duckdb.DuckDBPyConnection, csv_path: str, table: str) -> None:
    """Replace raw_nba.<table> with the contents of csv_path, adding ingested_at."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_nba")
    conn.execute(f"""
        CREATE OR REPLACE TABLE raw_nba.{table} AS
        SELECT *, now() AS ingested_at
        FROM read_csv_auto(?, sample_size=-1)
    """, [csv_path])

    count = conn.execute(f"SELECT count(*) FROM raw_nba.{table}").fetchone()[0]
    print(f"  Loaded {count:,} rows into raw_nba.{table}")
