from dagster import AssetSelection, define_asset_job

spotify_pipeline_job = define_asset_job(
    name="spotify_pipeline",
    selection=AssetSelection.groups("spotify_ingest") | AssetSelection.groups("spotify_dbt"),
    description="Ingest Spotify API data then run dbt staging + mart models",
)

statsbomb_pipeline_job = define_asset_job(
    name="statsbomb_pipeline",
    selection=(
        AssetSelection.groups("statsbomb_ingest") | AssetSelection.groups("statsbomb_dbt")
    ),
    description="Incrementally ingest StatsBomb open data then run dbt staging + mart models",
)

crypto_dbt_job = define_asset_job(
    name="crypto_dbt",
    selection=AssetSelection.groups("crypto_dbt"),
    description="Run dbt staging + OHLCV mart models over raw crypto trades",
)
