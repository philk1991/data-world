import duckdb
import spotipy
from datetime import datetime, timezone


def fetch_top_artists(client: spotipy.Spotify, time_range: str, limit: int = 50) -> list[dict]:
    """
    Fetch top artists for a given time range.
    time_range: short_term (~4 weeks), medium_term (~6 months), long_term (all time)
    """
    results = client.current_user_top_artists(time_range=time_range, limit=limit)
    artists = []
    for rank, item in enumerate(results["items"], start=1):
        artists.append({
            "id": item["id"],
            "name": item["name"],
            "rank": rank,
            "time_range": time_range,
            "popularity": item["popularity"],
            "followers": item["followers"]["total"],
            "genres": ", ".join(item["genres"]),
            "spotify_url": item["external_urls"]["spotify"],
            "image_url": item["images"][0]["url"] if item["images"] else None,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    return artists


def load_top_artists(conn: duckdb.DuckDBPyConnection, artists: list[dict]) -> None:
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
