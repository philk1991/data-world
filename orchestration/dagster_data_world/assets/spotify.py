from dagster import AssetExecutionContext, MaterializeResult, asset
from dagster_duckdb import DuckDBResource

# Import constants first — this adds data-ingestion/ to sys.path
import dagster_data_world.constants  # noqa: F401
from spotify.ingestion.top_artists import fetch_top_artists, load_top_artists
from spotify.ingestion.top_tracks import fetch_top_tracks, load_top_tracks
from spotify.ingestion.recently_played import fetch_recently_played, load_recently_played
from dagster_data_world.resources.spotify_client import SpotifyClientResource

_TIME_RANGES = ["short_term", "medium_term", "long_term"]


@asset(group_name="spotify_ingest", kinds={"python", "duckdb"})
def raw_spotify_top_artists(
    context: AssetExecutionContext,
    spotify: SpotifyClientResource,
    duckdb: DuckDBResource,
) -> MaterializeResult:
    client = spotify.get_client()
    total = 0
    with duckdb.get_connection() as conn:
        for time_range in _TIME_RANGES:
            artists = fetch_top_artists(client, time_range)
            load_top_artists(conn, artists)
            total += len(artists)
            context.log.info(f"Loaded {len(artists)} artists ({time_range})")
    return MaterializeResult(metadata={"row_count": total})


@asset(
    group_name="spotify_ingest",
    kinds={"python", "duckdb"},
    deps=[raw_spotify_top_artists],
)
def raw_spotify_top_tracks(
    context: AssetExecutionContext,
    spotify: SpotifyClientResource,
    duckdb: DuckDBResource,
) -> MaterializeResult:
    client = spotify.get_client()
    total = 0
    with duckdb.get_connection() as conn:
        for time_range in _TIME_RANGES:
            tracks = fetch_top_tracks(client, time_range)
            load_top_tracks(conn, tracks)
            total += len(tracks)
            context.log.info(f"Loaded {len(tracks)} tracks ({time_range})")
    return MaterializeResult(metadata={"row_count": total})


@asset(
    group_name="spotify_ingest",
    kinds={"python", "duckdb"},
    deps=[raw_spotify_top_tracks],
)
def raw_spotify_recently_played(
    context: AssetExecutionContext,
    spotify: SpotifyClientResource,
    duckdb: DuckDBResource,
) -> MaterializeResult:
    client = spotify.get_client()
    with duckdb.get_connection() as conn:
        plays = fetch_recently_played(client)
        load_recently_played(conn, plays)
    context.log.info(f"Loaded {len(plays)} recently played tracks")
    return MaterializeResult(metadata={"row_count": len(plays)})
