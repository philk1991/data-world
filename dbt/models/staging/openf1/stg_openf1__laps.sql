WITH source AS (
    SELECT *
    FROM
        {{ source('raw_openf1', 'raw_openf1_laps') }}
)

SELECT
    meeting_key,
    session_key,
    driver_number,
    lap_number,
    date_start::TIMESTAMP AS lap_start_at,
    lap_duration,
    duration_sector_1,
    duration_sector_2,
    duration_sector_3,
    i1_speed,
    i2_speed,
    st_speed,
    is_pit_out_lap,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
