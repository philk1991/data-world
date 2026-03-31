import duckdb
import spotipy
from datetime import datetime, timezone


def fetch_recommendations(
    client: spotipy.Spotify,
    seed_artist_ids: list[str],
    seed_track_ids: list[str],
    limit: int = 50,
) -> list[dict]:
    """
    Fetch track recommendations seeded from top artists and tracks.
    Spotify accepts up to 5 seeds total across artists, tracks, and genres.
    We use 3 top artists + 2 top tracks as seeds.
    """
    results = client.recommendations(
        seed_artists=seed_artist_ids[:3],
        seed_tracks=seed_track_ids[:2],
        limit=limit,
    )
    recs = []
    for item in results["tracks"]:
        recs.append({
            "track_id": item["id"],
            "track_name": item["name"],
            "artist_ids": ", ".join(a["id"] for a in item["artists"]),
            "artist_names": ", ".join(a["name"] for a in item["artists"]),
            "album_id": item["album"]["id"],
            "album_name": item["album"]["name"],
            "album_release_date": item["album"]["release_date"],
            "duration_ms": item["duration_ms"],
            "explicit": item["explicit"],
            "popularity": item["popularity"],
            "spotify_url": item["external_urls"]["spotify"],
            "preview_url": item.get("preview_url"),
            "seed_artist_ids": ", ".join(seed_artist_ids[:3]),
            "seed_track_ids": ", ".join(seed_track_ids[:2]),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    return recs


def load_recommendations(conn: duckdb.DuckDBPyConnection, recs: list[dict]) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_recommendations (
            track_id            VARCHAR,
            track_name          VARCHAR,
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
            seed_artist_ids     VARCHAR,
            seed_track_ids      VARCHAR,
            ingested_at         TIMESTAMPTZ
        )
    """)

    if recs:
        # Replace all recommendations on each run (seeds may change)
        conn.execute("DELETE FROM raw_recommendations")
        conn.executemany("""
            INSERT INTO raw_recommendations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            [
                r["track_id"], r["track_name"],
                r["artist_ids"], r["artist_names"],
                r["album_id"], r["album_name"], r["album_release_date"],
                r["duration_ms"], r["explicit"], r["popularity"],
                r["spotify_url"], r["preview_url"],
                r["seed_artist_ids"], r["seed_track_ids"],
                r["ingested_at"],
            ]
            for r in recs
        ])
        print(f"  Loaded {len(recs)} recommendations")
