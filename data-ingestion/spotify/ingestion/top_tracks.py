"""
Fetch and load top tracks from the Spotify API.

Spotify API reference: GET /me/top/tracks
  https://developer.spotify.com/documentation/web-api/reference/get-users-top-artists-and-tracks

Each call returns up to 50 tracks ordered by listening weight for the
requested time range. The pipeline calls this once per time range, giving
150 rows total before deduplication in the dbt mart layer.

DuckDB table: raw_top_tracks
  Rows are replaced per time_range on each run, so re-running is safe.

Note on album_release_date:
  Spotify returns release dates in three possible formats — "YYYY", "YYYY-MM",
  or "YYYY-MM-DD". The raw value is stored as VARCHAR here and normalised to a
  full date in the dbt staging model (stg_top_tracks).
"""
import duckdb
import spotipy
from datetime import datetime, timezone


def fetch_top_tracks(client: spotipy.Spotify, time_range: str, limit: int = 50) -> list[dict]:
    """Fetch the current user's top tracks for a given time range.

    Calls GET /me/top/tracks and flattens the response into plain dicts
    ready to be inserted into DuckDB.

    Args:
        client:     Authenticated Spotipy client (from spotify.auth.get_client).
        time_range: One of "short_term" (~4 weeks), "medium_term" (~6 months),
                    or "long_term" (all time).
        limit:      Number of tracks to fetch (max 50, Spotify API ceiling).

    Returns:
        List of dicts, one per track, with rank assigned 1 = most listened.
        Multi-artist tracks have artist IDs and names joined as comma-separated
        strings (Spotify can return multiple artists per track).
    """
    results = client.current_user_top_tracks(time_range=time_range, limit=limit)
    tracks = []
    for rank, item in enumerate(results["items"], start=1):
        tracks.append({
            "id": item["id"],
            "name": item["name"],
            "rank": rank,
            "time_range": time_range,
            "artist_ids": ", ".join(a["id"] for a in item["artists"]),     # comma-separated
            "artist_names": ", ".join(a["name"] for a in item["artists"]), # comma-separated
            "album_id": item["album"]["id"],
            "album_name": item["album"]["name"],
            "album_release_date": item["album"]["release_date"],  # raw: "YYYY", "YYYY-MM", or "YYYY-MM-DD"
            "duration_ms": item["duration_ms"],
            "explicit": item["explicit"],
            "popularity": item["popularity"],                      # Spotify score 0–100
            "spotify_url": item["external_urls"]["spotify"],
            "preview_url": item.get("preview_url"),                # null if Spotify has no preview
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    return tracks


def load_top_tracks(conn: duckdb.DuckDBPyConnection, tracks: list[dict]) -> None:
    """Upsert top tracks into DuckDB.

    Creates the raw_top_tracks table if it doesn't exist, deletes all
    existing rows for the given time_range, then bulk-inserts the new rows.
    This makes each run idempotent — re-running overwrites the previous
    snapshot for that time window rather than appending duplicates.

    Args:
        conn:   Open DuckDB connection.
        tracks: List of track dicts from fetch_top_tracks.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_top_tracks (
            id                  VARCHAR,
            name                VARCHAR,
            rank                INTEGER,
            time_range          VARCHAR,
            artist_ids          VARCHAR,
            artist_names        VARCHAR,
            album_id            VARCHAR,
            album_name          VARCHAR,
            album_release_date  VARCHAR,
            duration_ms         INTEGER,
            explicit            BOOLEAN,
            popularity          INTEGER,
            spotify_url         VARCHAR,
            preview_url         VARCHAR,
            ingested_at         TIMESTAMPTZ
        )
    """)

    if tracks:
        time_range = tracks[0]["time_range"]
        conn.execute("DELETE FROM raw_top_tracks WHERE time_range = ?", [time_range])
        conn.executemany("""
            INSERT INTO raw_top_tracks VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            [
                t["id"], t["name"], t["rank"], t["time_range"],
                t["artist_ids"], t["artist_names"],
                t["album_id"], t["album_name"], t["album_release_date"],
                t["duration_ms"], t["explicit"], t["popularity"],
                t["spotify_url"], t["preview_url"], t["ingested_at"],
            ]
            for t in tracks
        ])
        print(f"  Loaded {len(tracks)} tracks ({time_range})")
