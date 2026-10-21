WITH source AS (
    SELECT *
    FROM
        {{ source('raw_spotify', 'raw_top_artists') }}
)

SELECT
    id AS artist_id,
    name AS artist_name,
    rank,
    time_range,
    popularity,
    followers,
    genres,
    spotify_url,
    image_url,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
