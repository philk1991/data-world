-- Top tracks ranked across all three time periods side by side
WITH tracks AS (
    SELECT *
    FROM
        {{ ref('stg_top_tracks') }}
),

pivoted AS (
    SELECT
        track_id,
        track_name,
        artist_names,
        album_name,
        album_release_date,
        duration_minutes,
        explicit,
        MAX(popularity) AS popularity,
        MAX(CASE WHEN time_range = 'short_term' THEN rank END) AS rank_short_term,
        MAX(CASE WHEN time_range = 'medium_term' THEN rank END) AS rank_medium_term,
        MAX(CASE WHEN time_range = 'long_term' THEN rank END) AS rank_long_term,
        spotify_url,
        MAX(ingested_at) AS ingested_at
    FROM
        tracks
    GROUP BY
        track_id, track_name, artist_names, album_name,
        album_release_date, duration_minutes, explicit, spotify_url
)

SELECT *
FROM
    pivoted
ORDER BY
    COALESCE(rank_short_term, 999)
