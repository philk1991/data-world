WITH source AS (
    SELECT *
    FROM
        {{ source('raw_spotify', 'raw_top_tracks') }}
)

SELECT
    id AS track_id,
    name AS track_name,
    rank,
    time_range,
    artist_ids,
    artist_names,
    album_id,
    album_name,
    CASE
        WHEN LENGTH(album_release_date) = 4
            THEN (album_release_date || '-01-01')::DATE
        WHEN LENGTH(album_release_date) = 7
            THEN (album_release_date || '-01')::DATE
        ELSE album_release_date::DATE
    END AS album_release_date,
    duration_ms,
    ROUND(duration_ms / 60000.0, 2) AS duration_minutes,
    explicit,
    popularity,
    spotify_url,
    preview_url,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
