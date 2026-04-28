with source as (
    select * from {{ source('raw_spotify', 'raw_top_artists') }}
)

select
    id                                          as artist_id,
    name                                        as artist_name,
    rank,
    time_range,
    popularity,
    followers,
    genres,
    spotify_url,
    image_url,
    ingested_at::timestamp                      as ingested_at
from source
