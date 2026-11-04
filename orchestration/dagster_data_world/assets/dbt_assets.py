from dagster import AssetKey
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from dagster_data_world.constants import DBT_PROJECT_DIR

dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)
# manifest.json is pre-compiled via `task dbt:parse` (or any dbt run/build/compile).
# Run that task after adding or renaming models so Dagster picks up the changes.

# Maps dbt source node names → the Dagster ingest asset that writes them.
# This forces dbt assets to wait for Python ingest assets before running,
# preventing DuckDB write-lock contention within the same job.
_SOURCE_TO_ASSET: dict[str, AssetKey] = {
    "raw_top_artists": AssetKey(["raw_spotify_top_artists"]),
    "raw_top_tracks": AssetKey(["raw_spotify_top_tracks"]),
    "raw_recently_played": AssetKey(["raw_spotify_recently_played"]),
    "raw_sb_competitions": AssetKey(["raw_sb_competitions"]),
    "raw_sb_matches": AssetKey(["raw_sb_matches"]),
    "raw_sb_events": AssetKey(["raw_sb_events"]),
    "raw_sb_lineups": AssetKey(["raw_sb_lineups"]),
    # Each NBA source maps to its own full-replace ingest asset (same name).
    "raw_nba_games": AssetKey(["raw_nba_games"]),
    "raw_nba_player_statistics": AssetKey(["raw_nba_player_statistics"]),
    "raw_nba_team_statistics": AssetKey(["raw_nba_team_statistics"]),
    "raw_nba_players": AssetKey(["raw_nba_players"]),
    "raw_nba_team_histories": AssetKey(["raw_nba_team_histories"]),
    "raw_nba_player_statistics_extended": AssetKey(["raw_nba_player_statistics_extended"]),
    "raw_nba_team_statistics_extended": AssetKey(["raw_nba_team_statistics_extended"]),
    "raw_nba_play_by_play": AssetKey(["raw_nba_play_by_play"]),
}


class _DataWorldDbtTranslator(DagsterDbtTranslator):
    def get_group_name(self, dbt_resource_props: dict) -> str:
        path: str = dbt_resource_props.get("original_file_path", "")
        if "spotify" in path:
            return "spotify_dbt"
        if "statsbomb" in path:
            return "statsbomb_dbt"
        if "crypto" in path:
            return "crypto_dbt"
        if "nba" in path:
            return "nba_dbt"
        return "dbt"

    def get_asset_key(self, dbt_resource_props: dict) -> AssetKey:
        if dbt_resource_props.get("resource_type") == "source":
            name = dbt_resource_props.get("name", "")
            if name in _SOURCE_TO_ASSET:
                return _SOURCE_TO_ASSET[name]
        return super().get_asset_key(dbt_resource_props)


@dbt_assets(
    manifest=dbt_project.manifest_path,
    project=dbt_project,
    select="package:spotify",  # all user models; excludes installed packages (dbt_utils)
    dagster_dbt_translator=_DataWorldDbtTranslator(),
)
def all_dbt_assets(context, dbt: DbtCliResource):
    invocation = dbt.cli(["build"], context=context)
    for event in invocation.stream_raw_events():
        # dbt-oss emits Fusion-style events, and dagster-dbt's Fusion parser looks unit
        # tests up in manifest["nodes"] (they live in manifest["unit_tests"]), raising
        # KeyError. Skip their events; a failing unit test still fails the step, because
        # stream_raw_events() raises on dbt's non-zero exit code.
        unique_id = event.raw_event["data"].get("node_info", {}).get("unique_id", "")
        if unique_id.startswith("unit_test."):
            continue
        yield from event.to_default_asset_events(
            manifest=invocation.manifest,
            dagster_dbt_translator=invocation.dagster_dbt_translator,
            context=context,
            target_path=invocation.target_path,
            project=invocation.project,
        )
