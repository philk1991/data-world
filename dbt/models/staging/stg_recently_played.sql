with source as (
    select * from {{ source('raw', 'raw_recently_played') }}
)

select
    played_at::timestamp                        as played_at,
    date_trunc('day', played_at::timestamp)     as played_date,
    date_part('hour', played_at::timestamp)     as played_hour,
    track_id,
    track_name,
    artist_ids,
    artist_names,
    album_id,
    album_name,
    duration_ms,
    round(duration_ms / 60000.0, 2)            as duration_minutes,
    explicit,
    popularity,
    spotify_url,
    context_type,
    context_uri,
    ingested_at::timestamp                      as ingested_at
from source
