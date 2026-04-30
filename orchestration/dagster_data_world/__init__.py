from dagster import Definitions, EnvVar
from dagster_dbt import DbtCliResource
from dagster_duckdb import DuckDBResource

from dagster_data_world.assets import (
    raw_spotify_top_artists,
    raw_spotify_top_tracks,
    raw_spotify_recently_played,
    raw_sb_competitions,
    raw_sb_matches,
    raw_sb_events,
    raw_sb_lineups,
    all_dbt_assets,
    dbt_project,
)
from dagster_data_world.resources import SpotifyClientResource
from dagster_data_world.jobs import spotify_pipeline_job, statsbomb_pipeline_job, crypto_dbt_job
from dagster_data_world.schedules import spotify_daily_schedule, statsbomb_weekly_schedule
from dagster_data_world.sensors.crypto_sensor import crypto_new_data_sensor
from dagster_data_world.constants import DUCKDB_PATH, DBT_PROJECT_DIR

defs = Definitions(
    assets=[
        raw_spotify_top_artists,
        raw_spotify_top_tracks,
        raw_spotify_recently_played,
        raw_sb_competitions,
        raw_sb_matches,
        raw_sb_events,
        raw_sb_lineups,
        all_dbt_assets,
    ],
    resources={
        "duckdb": DuckDBResource(database=DUCKDB_PATH),
        "spotify": SpotifyClientResource(
            client_id=EnvVar("SPOTIFY_CLIENT_ID"),
            client_secret=EnvVar("SPOTIFY_CLIENT_SECRET"),
        ),
        "dbt": DbtCliResource(
            project_dir=dbt_project,
            profiles_dir=str(DBT_PROJECT_DIR),
        ),
    },
    jobs=[spotify_pipeline_job, statsbomb_pipeline_job, crypto_dbt_job],
    schedules=[spotify_daily_schedule, statsbomb_weekly_schedule],
    sensors=[crypto_new_data_sensor],
)
