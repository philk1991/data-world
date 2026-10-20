from contextlib import contextmanager
from typing import Iterator

import duckdb
from dagster import ConfigurableResource

import dagster_data_world.constants  # noqa: F401 — adds data-ingestion/ to sys.path
from lake import connect_lake


class LakeResource(ConfigurableResource):
    """Connection to the shared DuckLake (Postgres catalog + Parquet in data/lake/).

    Wraps data-ingestion/lake.py's connect_lake(), so assets get the same
    `lake` attach and `USE lake` as the standalone ingest scripts. Mirrors
    DuckDBResource's get_connection() context-manager interface.
    """

    read_only: bool = False

    @contextmanager
    def get_connection(self) -> Iterator[duckdb.DuckDBPyConnection]:
        conn = connect_lake(read_only=self.read_only)
        try:
            yield conn
        finally:
            conn.close()
