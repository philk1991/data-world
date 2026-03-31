-- Top tracks ranked across all three time periods side by side
with tracks as (
    select * from {{ ref('stg_top_tracks') }}
),

pivoted as (
    select
        track_id,
        track_name,
        artist_names,
        album_name,
        album_release_date,
        duration_minutes,
        explicit,
        max(popularity)                                                         as popularity,
        max(case when time_range = 'short_term'  then rank end)                as rank_short_term,
        max(case when time_range = 'medium_term' then rank end)                as rank_medium_term,
        max(case when time_range = 'long_term'   then rank end)                as rank_long_term,
        spotify_url,
        max(ingested_at)                                                        as ingested_at
    from tracks
    group by track_id, track_name, artist_names, album_name,
             album_release_date, duration_minutes, explicit, spotify_url
)

select * from pivoted
order by coalesce(rank_short_term, 999)
