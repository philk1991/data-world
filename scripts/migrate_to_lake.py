#!/usr/bin/env python3
"""
Copy every raw_* table from the old spotify.duckdb file into the DuckLake.

Before:  data/spotify.duckdb → raw_spotify.*, raw_nba.*, raw_openf1.*, raw_statsbomb.*
After:   the same schemas and tables inside the lake (see data-ingestion/lake.py)

Only raw tables are copied: staging and marts are rebuilt by dbt, so copying them
would just be overwritten. Copying saves re-ingesting, which matters for OpenF1 in
particular (hours of rate-limited API calls).

The old file is attached READ_ONLY, so this script cannot modify it. Each lake
table is replaced (CREATE OR REPLACE), so re-running is safe. Row counts are
compared table by table, and the script exits non-zero on any mismatch.

Usage (run from project root, after `task lake:init`):
    python scripts/migrate_to_lake.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "data-ingestion"))
from lake import connect_lake  # noqa: E402

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "spotify.duckdb")


def main() -> None:
    db_path = os.environ.get("DUCKDB_PATH", _DEFAULT_DB_PATH)
    print(f"Copying raw tables from {db_path} (read-only) into the lake\n")

    conn = connect_lake()
    conn.execute(f"ATTACH '{db_path}' AS old (READ_ONLY)")
    tables = conn.execute("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_catalog = 'old' AND table_schema LIKE 'raw\\_%' ESCAPE '\\'
          AND table_type = 'BASE TABLE'
        ORDER BY 1, 2
    """).fetchall()

    mismatches = []
    for schema, table in tables:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS lake.{schema}")
        conn.execute(f"CREATE OR REPLACE TABLE lake.{schema}.{table} AS SELECT * FROM old.{schema}.{table}")
        old_count = conn.execute(f"SELECT count(*) FROM old.{schema}.{table}").fetchone()[0]
        new_count = conn.execute(f"SELECT count(*) FROM lake.{schema}.{table}").fetchone()[0]
        status = "OK" if old_count == new_count else "MISMATCH"
        if status == "MISMATCH":
            mismatches.append(f"{schema}.{table}")
        print(f"  {status:8s} {schema}.{table}: {old_count:,} → {new_count:,}")

    conn.close()
    print(f"\n{len(tables)} tables copied, {len(mismatches)} mismatches.")
    if mismatches:
        print("Mismatched tables: " + ", ".join(mismatches))
        sys.exit(1)


if __name__ == "__main__":
    main()
