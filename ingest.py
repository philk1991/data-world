#!/usr/bin/env python3
"""
Main ingestion script — pulls top artists and tracks from Spotify
and loads them into DuckDB.

Usage:
    python ingest.py
"""
import os
import duckdb
from dotenv import load_dotenv

from spotify.auth import get_client
from spotify.ingestion.top_artists import fetch_top_artists, load_top_artists
from spotify.ingestion.top_tracks import fetch_top_tracks, load_top_tracks

load_dotenv()

TIME_RANGES = ["short_term", "medium_term", "long_term"]


def main():
    db_path = os.environ.get("DUCKDB_PATH", "./data/spotify.duckdb")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    print("Authenticating with Spotify...")
    client = get_client()
    me = client.me()
    print(f"Logged in as: {me['display_name']} ({me['id']})\n")

    conn = duckdb.connect(db_path)

    print("Fetching top artists...")
    for time_range in TIME_RANGES:
        artists = fetch_top_artists(client, time_range)
        load_top_artists(conn, artists)

    print("\nFetching top tracks...")
    for time_range in TIME_RANGES:
        tracks = fetch_top_tracks(client, time_range)
        load_top_tracks(conn, tracks)

    conn.close()
    print(f"\nDone. Data written to {db_path}")


if __name__ == "__main__":
    main()
