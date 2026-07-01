with source as (
    select * from {{ source('raw_openf1', 'raw_openf1_laps') }}
)

select
    meeting_key,
    session_key,
    driver_number,
    lap_number,
    date_start::timestamp                     as lap_start_at,
    lap_duration,
    duration_sector_1,
    duration_sector_2,
    duration_sector_3,
    i1_speed,
    i2_speed,
    st_speed,
    is_pit_out_lap,
    ingested_at::timestamp                    as ingested_at
from source
