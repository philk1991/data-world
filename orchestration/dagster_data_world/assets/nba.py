from dagster import AssetExecutionContext, AssetKey, MaterializeResult, asset
from dagster_duckdb import DuckDBResource

import dagster_data_world.constants  # noqa: F401 — adds data-ingestion/ to sys.path
from nba.ingestion.download import download_file
from nba.ingestion.load import load_csv
from ingest_nba import FILE_TABLE_MAP


def _make_nba_asset(filename: str, table: str, upstream: str | None):
    """Build one ingest asset that full-replaces raw_nba.<table> from a Kaggle file.

    Each asset is chained to the previous one via `upstream` so the seven
    full-replace loads run serially in a single run and never contend for the
    DuckDB write lock (see the DuckDB constraints in CLAUDE.md).
    """

    @asset(
        name=table,
        group_name="nba_ingest",
        kinds={"python", "duckdb"},
        deps=[AssetKey([upstream])] if upstream else [],
    )
    def _nba_asset(
        context: AssetExecutionContext,
        duckdb: DuckDBResource,
    ) -> MaterializeResult:
        path = download_file(filename)
        if path is None:
            context.log.warning(
                f"Download failed for {filename}; raw_nba.{table} not refreshed"
            )
            return MaterializeResult(metadata={"row_count": 0, "skipped": True})
        with duckdb.get_connection() as conn:
            load_csv(conn, path, table)
            row_count = conn.execute(
                f"SELECT count(*) FROM raw_nba.{table}"
            ).fetchone()[0]
        context.log.info(f"Loaded {row_count} rows into raw_nba.{table}")
        return MaterializeResult(metadata={"row_count": row_count})

    return _nba_asset


# Build the chain in FILE_TABLE_MAP (insertion) order so re-runs pick up the
# daily-updated Kaggle snapshot for every table.
nba_assets = []
_prev: str | None = None
for _filename, _table in FILE_TABLE_MAP.items():
    nba_assets.append(_make_nba_asset(_filename, _table, _prev))
    _prev = _table
