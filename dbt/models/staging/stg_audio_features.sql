with source as (
    select * from {{ source('raw', 'raw_audio_features') }}
)

select
    track_id,
    danceability,
    energy,
    key,
    loudness,
    mode,
    speechiness,
    acousticness,
    instrumentalness,
    liveness,
    valence,
    tempo,
    time_signature,
    ingested_at::timestamp                      as ingested_at
from source
