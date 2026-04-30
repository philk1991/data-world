from dagster import AssetExecutionContext, MaterializeResult, asset
from dagster_duckdb import DuckDBResource

import dagster_data_world.constants  # noqa: F401 — adds data-ingestion/ to sys.path
from statsbomb.ingestion.competitions import fetch_competitions, load_competitions
from statsbomb.ingestion.matches import fetch_matches, load_matches
from statsbomb.ingestion.events import (
    fetch_events,
    load_events,
    get_loaded_match_ids as get_loaded_event_ids,
)
from statsbomb.ingestion.lineups import (
    fetch_lineups,
    load_lineups,
    get_loaded_match_ids as get_loaded_lineup_ids,
)


@asset(group_name="statsbomb_ingest", kinds={"python", "duckdb"})
def raw_sb_competitions(
    context: AssetExecutionContext,
    duckdb: DuckDBResource,
) -> MaterializeResult:
    competitions = fetch_competitions()
    with duckdb.get_connection() as conn:
        load_competitions(conn, competitions)
    context.log.info(f"Loaded {len(competitions)} competitions")
    return MaterializeResult(metadata={"row_count": len(competitions)})


@asset(group_name="statsbomb_ingest", kinds={"python", "duckdb"}, deps=[raw_sb_competitions])
def raw_sb_matches(
    context: AssetExecutionContext,
    duckdb: DuckDBResource,
) -> MaterializeResult:
    competitions = fetch_competitions()
    total = 0
    with duckdb.get_connection() as conn:
        for comp in competitions:
            matches = fetch_matches(comp["competition_id"], comp["season_id"])
            load_matches(conn, matches, comp["competition_id"], comp["season_id"])
            total += len(matches)
    context.log.info(f"Loaded {total} matches across {len(competitions)} competitions")
    return MaterializeResult(metadata={"row_count": total})


@asset(group_name="statsbomb_ingest", kinds={"python", "duckdb"}, deps=[raw_sb_matches])
def raw_sb_events(
    context: AssetExecutionContext,
    duckdb: DuckDBResource,
) -> MaterializeResult:
    new_rows = 0
    with duckdb.get_connection() as conn:
        loaded_ids = get_loaded_event_ids(conn)
        all_match_ids = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT match_id FROM raw_statsbomb.raw_sb_matches"
                " WHERE match_status = 'available'"
            ).fetchall()
        ]
        for match_id in all_match_ids:
            if match_id not in loaded_ids:
                events = fetch_events(match_id)
                load_events(conn, events, match_id)
                new_rows += len(events)
    context.log.info(f"Loaded {new_rows} new event rows (incremental)")
    return MaterializeResult(metadata={"new_rows": new_rows})


@asset(group_name="statsbomb_ingest", kinds={"python", "duckdb"}, deps=[raw_sb_events])
def raw_sb_lineups(
    context: AssetExecutionContext,
    duckdb: DuckDBResource,
) -> MaterializeResult:
    new_rows = 0
    with duckdb.get_connection() as conn:
        loaded_ids = get_loaded_lineup_ids(conn)
        all_match_ids = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT match_id FROM raw_statsbomb.raw_sb_matches"
                " WHERE match_status = 'available'"
            ).fetchall()
        ]
        for match_id in all_match_ids:
            if match_id not in loaded_ids:
                lineups = fetch_lineups(match_id)
                load_lineups(conn, lineups, match_id)
                new_rows += len(lineups)
    context.log.info(f"Loaded {new_rows} new lineup rows (incremental)")
    return MaterializeResult(metadata={"new_rows": new_rows})
