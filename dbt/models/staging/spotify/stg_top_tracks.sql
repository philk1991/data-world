with source as (
    select * from {{ source('raw_spotify', 'raw_top_tracks') }}
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
    case
        when length(album_release_date) = 4
        then (album_release_date || '-01-01')::date
        when length(album_release_date) = 7
        then (album_release_date || '-01')::date
        else album_release_date::date
    end                                         as album_release_date,
    duration_ms,
    round(duration_ms / 60000.0, 2)            as duration_minutes,
    explicit,
    popularity,
    spotify_url,
    preview_url,
    ingested_at::timestamp                      as ingested_at
from source
