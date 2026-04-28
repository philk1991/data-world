# data-ingestion

Pulls your top artists and tracks from the Spotify API and loads them into a local DuckDB database.

## How it works

```
Spotify API
    │
    │  GET /me/top/artists  (×3 time ranges)
    │  GET /me/top/tracks   (×3 time ranges)
    ▼
spotify/auth.py          — OAuth token management (Spotipy + browser flow)
spotify/ingestion/       — fetch → flatten → upsert per resource type
    top_artists.py
    top_tracks.py
    │
    ▼
DuckDB  ../data/spotify.duckdb
    raw_top_artists   (up to 150 rows — 50 per time range)
    raw_top_tracks    (up to 150 rows — 50 per time range)
```

Each run replaces the existing rows for each time range, so re-running is always safe.

## Setup

### 1. Create a Spotify Developer app

1. Go to <https://developer.spotify.com/dashboard> and create a new app.
2. In the app settings, add `http://localhost:8888/callback` as a **Redirect URI**.
3. Note your **Client ID** and **Client Secret**.

### 2. Configure environment variables

Copy `.env.example` (at the project root) to `.env` and fill in your credentials:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback   # optional, this is the default
DUCKDB_PATH=../data/spotify.duckdb                    # optional, this is the default
```

### 3. Install dependencies

```bash
pip install -r ../requirements.txt
```

### 4. Run

```bash
cd data-ingestion
python ingest.py
```

On first run a browser tab opens for Spotify login. After granting access the token is cached in `.spotify_cache` — subsequent runs are fully automated.

## Time ranges

| Value         | Spotify description  |
|---------------|----------------------|
| `short_term`  | ~last 4 weeks        |
| `medium_term` | ~last 6 months       |
| `long_term`   | All time             |

## Output tables

### `raw_top_artists`

| Column       | Type        | Notes                              |
|--------------|-------------|------------------------------------|
| id           | VARCHAR     | Spotify artist ID                  |
| name         | VARCHAR     |                                    |
| rank         | INTEGER     | 1 = most listened                  |
| time_range   | VARCHAR     | short / medium / long _term        |
| popularity   | INTEGER     | Spotify score 0–100                |
| followers    | INTEGER     |                                    |
| genres       | VARCHAR     | Comma-separated                    |
| spotify_url  | VARCHAR     |                                    |
| image_url    | VARCHAR     | Null if artist has no image        |
| ingested_at  | TIMESTAMPTZ | UTC timestamp of this run          |

### `raw_top_tracks`

| Column             | Type        | Notes                                      |
|--------------------|-------------|--------------------------------------------|
| id                 | VARCHAR     | Spotify track ID                           |
| name               | VARCHAR     |                                            |
| rank               | INTEGER     | 1 = most listened                          |
| time_range         | VARCHAR     | short / medium / long _term                |
| artist_ids         | VARCHAR     | Comma-separated Spotify artist IDs         |
| artist_names       | VARCHAR     | Comma-separated artist names               |
| album_id           | VARCHAR     |                                            |
| album_name         | VARCHAR     |                                            |
| album_release_date | VARCHAR     | Raw from API — "YYYY", "YYYY-MM", or full date; normalised in dbt |
| duration_ms        | INTEGER     |                                            |
| explicit           | BOOLEAN     |                                            |
| popularity         | INTEGER     | Spotify score 0–100                        |
| spotify_url        | VARCHAR     |                                            |
| preview_url        | VARCHAR     | Null if Spotify has no 30s preview         |
| ingested_at        | TIMESTAMPTZ | UTC timestamp of this run                  |

## Code layout

```
data-ingestion/
├── ingest.py                      # Entry point — orchestrates fetch + load
└── spotify/
    ├── auth.py                    # get_client() — OAuth setup
    └── ingestion/
        ├── top_artists.py         # fetch_top_artists / load_top_artists
        └── top_tracks.py          # fetch_top_tracks  / load_top_tracks
```
