import duckdb
import spotipy
from datetime import datetime, timezone


def fetch_audio_features(client: spotipy.Spotify, track_ids: list[str]) -> list[dict]:
    """
    Fetch audio features for a list of track IDs.
    Spotify allows up to 100 IDs per request.
    """
    features = []
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i:i + 100]
        results = client.audio_features(batch)
        for item in results:
            if item is None:
                continue
            features.append({
                "track_id": item["id"],
                "danceability": item["danceability"],
                "energy": item["energy"],
                "key": item["key"],
                "loudness": item["loudness"],
                "mode": item["mode"],
                "speechiness": item["speechiness"],
                "acousticness": item["acousticness"],
                "instrumentalness": item["instrumentalness"],
                "liveness": item["liveness"],
                "valence": item["valence"],
                "tempo": item["tempo"],
                "time_signature": item["time_signature"],
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            })
    return features


def load_audio_features(conn: duckdb.DuckDBPyConnection, features: list[dict]) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_audio_features (
            track_id          VARCHAR PRIMARY KEY,
            danceability      DOUBLE,
            energy            DOUBLE,
            key               INTEGER,
            loudness          DOUBLE,
            mode              INTEGER,
            speechiness       DOUBLE,
            acousticness      DOUBLE,
            instrumentalness  DOUBLE,
            liveness          DOUBLE,
            valence           DOUBLE,
            tempo             DOUBLE,
            time_signature    INTEGER,
            ingested_at       TIMESTAMPTZ
        )
    """)

    if features:
        track_ids = [f["track_id"] for f in features]
        conn.execute(
            f"DELETE FROM raw_audio_features WHERE track_id IN ({','.join(['?'] * len(track_ids))})",
            track_ids,
        )
        conn.executemany("""
            INSERT INTO raw_audio_features VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            [
                f["track_id"], f["danceability"], f["energy"], f["key"],
                f["loudness"], f["mode"], f["speechiness"], f["acousticness"],
                f["instrumentalness"], f["liveness"], f["valence"],
                f["tempo"], f["time_signature"], f["ingested_at"],
            ]
            for f in features
        ])
        print(f"  Loaded audio features for {len(features)} tracks")
