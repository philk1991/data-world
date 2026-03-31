-- Top artists ranked across all three time periods side by side
with artists as (
    select * from {{ ref('stg_top_artists') }}
),

pivoted as (
    select
        artist_id,
        artist_name,
        genres,
        max(popularity)                                                         as popularity,
        max(followers)                                                          as followers,
        max(case when time_range = 'short_term'  then rank end)                as rank_short_term,
        max(case when time_range = 'medium_term' then rank end)                as rank_medium_term,
        max(case when time_range = 'long_term'   then rank end)                as rank_long_term,
        spotify_url,
        max(ingested_at)                                                        as ingested_at
    from artists
    group by artist_id, artist_name, genres, spotify_url
)

select * from pivoted
order by coalesce(rank_short_term, 999)
