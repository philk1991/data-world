import duckdb
import spotipy
from datetime import datetime, timezone


def fetch_recently_played(client: spotipy.Spotify, limit: int = 50) -> list[dict]:
    """
    Fetch the user's 50 most recently played tracks.
    Each row is a distinct play event, identified by played_at.
    """
    results = client.current_user_recently_played(limit=limit)
    plays = []
    for item in results["items"]:
        track = item["track"]
        context = item.get("context") or {}
        plays.append({
            "played_at": item["played_at"],
            "track_id": track["id"],
            "track_name": track["name"],
            "artist_ids": ", ".join(a["id"] for a in track["artists"]),
            "artist_names": ", ".join(a["name"] for a in track["artists"]),
            "album_id": track["album"]["id"],
            "album_name": track["album"]["name"],
            "duration_ms": track["duration_ms"],
            "explicit": track["explicit"],
            "popularity": track["popularity"],
            "spotify_url": track["external_urls"]["spotify"],
            "context_type": context.get("type"),
            "context_uri": context.get("uri"),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    return plays


def load_recently_played(conn: duckdb.DuckDBPyConnection, plays: list[dict]) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_recently_played (
            played_at     TIMESTAMPTZ,
            track_id      VARCHAR,
            track_name    VARCHAR,
            artist_ids    VARCHAR,
            artist_names  VARCHAR,
            album_id      VARCHAR,
            album_name    VARCHAR,
            duration_ms   INTEGER,
            explicit      BOOLEAN,
            popularity    INTEGER,
            spotify_url   VARCHAR,
            context_type  VARCHAR,
            context_uri   VARCHAR,
            ingested_at   TIMESTAMPTZ
        )
    """)

    if plays:
        played_ats = [p["played_at"] for p in plays]
        conn.execute(
            f"DELETE FROM raw_recently_played WHERE played_at IN ({','.join(['?'] * len(played_ats))})",
            played_ats,
        )
        conn.executemany("""
            INSERT INTO raw_recently_played VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            [
                p["played_at"], p["track_id"], p["track_name"],
                p["artist_ids"], p["artist_names"],
                p["album_id"], p["album_name"],
                p["duration_ms"], p["explicit"], p["popularity"],
                p["spotify_url"], p["context_type"], p["context_uri"],
                p["ingested_at"],
            ]
            for p in plays
        ])
        print(f"  Loaded {len(plays)} recently played tracks")
