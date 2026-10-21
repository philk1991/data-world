WITH source AS (
    SELECT *
    FROM
        {{ source('raw_openf1', 'raw_openf1_drivers') }}
)

SELECT
    meeting_key,
    session_key,
    driver_number,
    broadcast_name,
    full_name,
    name_acronym,
    team_name,
    team_colour,
    first_name,
    last_name,
    country_code,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
