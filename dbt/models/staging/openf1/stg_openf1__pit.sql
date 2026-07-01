with source as (
    select * from {{ source('raw_openf1', 'raw_openf1_pit') }}
)

select
    session_key,
    meeting_key,
    driver_number,
    lap_number,
    "date"::timestamp                         as pit_at,
    pit_duration,
    stop_duration,
    lane_duration,
    ingested_at::timestamp                    as ingested_at
from source
