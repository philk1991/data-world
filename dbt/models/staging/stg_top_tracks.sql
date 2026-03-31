with source as (
    select * from {{ source('raw', 'raw_top_tracks') }}
)

select
    id                                          as track_id,
    name                                        as track_name,
    rank,
    time_range,
    artist_ids,
    artist_names,
    album_id,
    album_name,
    album_release_date::date                    as album_release_date,
    duration_ms,
    round(duration_ms / 60000.0, 2)            as duration_minutes,
    explicit,
    popularity,
    spotify_url,
    preview_url,
    ingested_at::timestamp                      as ingested_at
from source
