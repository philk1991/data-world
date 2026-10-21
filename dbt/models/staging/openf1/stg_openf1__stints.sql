WITH source AS (
    SELECT *
    FROM
        {{ source('raw_openf1', 'raw_openf1_stints') }}
)

SELECT
    meeting_key,
    session_key,
    driver_number,
    stint_number,
    lap_start,
    lap_end,
    compound,
    tyre_age_at_start,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
