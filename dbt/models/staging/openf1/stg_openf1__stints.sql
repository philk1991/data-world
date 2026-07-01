with source as (
    select * from {{ source('raw_openf1', 'raw_openf1_stints') }}
)

select
    meeting_key,
    session_key,
    driver_number,
    stint_number,
    lap_start,
    lap_end,
    compound,
    tyre_age_at_start,
    ingested_at::timestamp                    as ingested_at
from source
