WITH source AS (
    SELECT *
    FROM
        {{ source('raw_openf1', 'raw_openf1_pit') }}
)

SELECT
    session_key,
    meeting_key,
    driver_number,
    lap_number,
    date::TIMESTAMP AS pit_at,
    pit_duration,
    stop_duration,
    lane_duration,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
