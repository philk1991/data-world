"""
Ingestion modules — one module per Spotify resource type.

Each module exposes two functions:
  fetch_*  — calls the Spotify API and returns a list of dicts
  load_*   — creates the DuckDB table if needed and upserts the rows
"""
