WITH source AS (
    SELECT *
    FROM
        {{ source('raw_spotify', 'raw_recently_played') }}
)

SELECT
    played_at::TIMESTAMP AS played_at,
    DATE_TRUNC('day', played_at::TIMESTAMP) AS played_date,
    DATE_PART('hour', played_at::TIMESTAMP) AS played_hour,
    track_id,
    track_name,
    artist_ids,
    artist_names,
    album_id,
    album_name,
    duration_ms,
    ROUND(duration_ms / 60000.0, 2) AS duration_minutes,
    explicit,
    popularity,
    spotify_url,
    context_type,
    context_uri,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
