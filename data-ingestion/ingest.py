#!/usr/bin/env python3
"""
Main ingestion script — pulls data from Spotify and loads into DuckDB.

Fetches:
  - Top 50 artists × 3 time ranges  (short_term, medium_term, long_term)
  - Top 50 tracks  × 3 time ranges
  - 50 most recently played tracks

Configuration (via .env at the project root or environment variables):
  SPOTIFY_CLIENT_ID      — from your Spotify Developer app
  SPOTIFY_CLIENT_SECRET  — from your Spotify Developer app
  SPOTIFY_REDIRECT_URI   — defaults to http://127.0.0.1:8888/callback
  DUCKDB_PATH            — path to the DuckDB file, defaults to ../data/spotify.duckdb

Usage (run from data-ingestion/):
    python ingest.py
"""
import os
from pathlib import Path
import duckdb
from dotenv import load_dotenv

from spotify.auth import get_client
from spotify.ingestion.top_artists import fetch_top_artists, load_top_artists
from spotify.ingestion.top_tracks import fetch_top_tracks, load_top_tracks
from spotify.ingestion.recently_played import fetch_recently_played, load_recently_played

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

TIME_RANGES = ["short_term", "medium_term", "long_term"]

_DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "spotify.duckdb")


def main():
    db_path = os.environ.get("DUCKDB_PATH", _DEFAULT_DB_PATH)
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

    print("\nFetching recently played...")
    plays = fetch_recently_played(client)
    load_recently_played(conn, plays)

    conn.close()
    print(f"\nDone. Data written to {db_path}")


if __name__ == "__main__":
    main()
