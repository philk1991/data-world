import duckdb
import spotipy
from datetime import datetime, timezone


def fetch_top_tracks(client: spotipy.Spotify, time_range: str, limit: int = 50) -> list[dict]:
    """
    Fetch top tracks for a given time range.
    time_range: short_term (~4 weeks), medium_term (~6 months), long_term (all time)
    """
    results = client.current_user_top_tracks(time_range=time_range, limit=limit)
    tracks = []
    for rank, item in enumerate(results["items"], start=1):
        tracks.append({
            "id": item["id"],
            "name": item["name"],
            "rank": rank,
            "time_range": time_range,
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
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    return tracks


def load_top_tracks(conn: duckdb.DuckDBPyConnection, tracks: list[dict]) -> None:
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
