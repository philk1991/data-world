with source as (
    select * from {{ source('raw', 'raw_recommendations') }}
)

select
    track_id,
    track_name,
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
    seed_artist_ids,
    seed_track_ids,
    ingested_at::timestamp                      as ingested_at
from source
