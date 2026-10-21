WITH source AS (
    SELECT *
    FROM
        {{ source('raw_openf1', 'raw_openf1_weather') }}
)

SELECT
    session_key,
    meeting_key,
    date::TIMESTAMP AS observed_at,
    air_temperature,
    track_temperature,
    humidity,
    pressure,
    rainfall,
    wind_direction,
    wind_speed,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
