with source as (
    select * from {{ source('raw_openf1', 'raw_openf1_weather') }}
)

select
    session_key,
    meeting_key,
    "date"::timestamp                         as observed_at,
    air_temperature,
    track_temperature,
    humidity,
    pressure,
    rainfall,
    wind_direction,
    wind_speed,
    ingested_at::timestamp                    as ingested_at
from source
