-- Top artists ranked across all three time periods side by side
WITH artists AS (
    SELECT *
    FROM
        {{ ref('stg_top_artists') }}
),

pivoted AS (
    SELECT
        artist_id,
        artist_name,
        genres,
        MAX(popularity) AS popularity,
        MAX(followers) AS followers,
        MAX(image_url) AS image_url,
        MAX(CASE WHEN time_range = 'short_term' THEN rank END) AS rank_short_term,
        MAX(CASE WHEN time_range = 'medium_term' THEN rank END) AS rank_medium_term,
        MAX(CASE WHEN time_range = 'long_term' THEN rank END) AS rank_long_term,
        spotify_url,
        MAX(ingested_at) AS ingested_at
    FROM
        artists
    GROUP BY
        artist_id, artist_name, genres, spotify_url
)

SELECT *
FROM
    pivoted
ORDER BY
    COALESCE(rank_short_term, 999)
