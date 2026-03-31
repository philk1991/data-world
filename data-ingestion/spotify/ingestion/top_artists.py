"""
Fetch and load top artists from the Spotify API.

Spotify API reference: GET /me/top/artists
  https://developer.spotify.com/documentation/web-api/reference/get-users-top-artists-and-tracks

Each call returns up to 50 artists ordered by listening weight for the
requested time range. The pipeline calls this once per time range, giving
150 rows total before deduplication in the dbt mart layer.

DuckDB table: raw_top_artists
  Rows are replaced per time_range on each run, so re-running is safe.
"""
import duckdb
import spotipy
from datetime import datetime, timezone


def fetch_top_artists(client: spotipy.Spotify, time_range: str, limit: int = 50) -> list[dict]:
    """Fetch the current user's top artists for a given time range.

    Calls GET /me/top/artists and flattens the response into plain dicts
    ready to be inserted into DuckDB.

    Args:
        client:     Authenticated Spotipy client (from spotify.auth.get_client).
        time_range: One of "short_term" (~4 weeks), "medium_term" (~6 months),
                    or "long_term" (all time).
        limit:      Number of artists to fetch (max 50, Spotify API ceiling).

    Returns:
        List of dicts, one per artist, with rank assigned 1 = most listened.
    """
    results = client.current_user_top_artists(time_range=time_range, limit=limit)
    artists = []
    for rank, item in enumerate(results["items"], start=1):
        artists.append({
            "id": item["id"],
            "name": item["name"],
            "rank": rank,
            "time_range": time_range,
            "popularity": item["popularity"],              # Spotify score 0–100
            "followers": item["followers"]["total"],
            "genres": ", ".join(item["genres"]),           # comma-separated string
            "spotify_url": item["external_urls"]["spotify"],
            "image_url": item["images"][0]["url"] if item["images"] else None,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    return artists


def load_top_artists(conn: duckdb.DuckDBPyConnection, artists: list[dict]) -> None:
    """Upsert top artists into DuckDB.

    Creates the raw_top_artists table if it doesn't exist, deletes all
    existing rows for the given time_range, then bulk-inserts the new rows.
    This makes each run idempotent — re-running overwrites the previous
    snapshot for that time window rather than appending duplicates.

    Args:
        conn:    Open DuckDB connection.
        artists: List of artist dicts from fetch_top_artists.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_top_artists (
            id             VARCHAR,
            name           VARCHAR,
            rank           INTEGER,
            time_range     VARCHAR,
            popularity     INTEGER,
            followers      INTEGER,
            genres         VARCHAR,
            spotify_url    VARCHAR,
            image_url      VARCHAR,
            ingested_at    TIMESTAMPTZ
        )
    """)

    # Replace existing rows for this time_range so re-runs are idempotent
    if artists:
        time_range = artists[0]["time_range"]
        conn.execute("DELETE FROM raw_top_artists WHERE time_range = ?", [time_range])
        conn.executemany("""
            INSERT INTO raw_top_artists VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            [
                a["id"], a["name"], a["rank"], a["time_range"],
                a["popularity"], a["followers"], a["genres"],
                a["spotify_url"], a["image_url"], a["ingested_at"],
            ]
            for a in artists
        ])
        print(f"  Loaded {len(artists)} artists ({time_range})")
