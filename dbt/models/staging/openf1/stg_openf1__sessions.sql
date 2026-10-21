WITH source AS (
    SELECT *
    FROM
        {{ source('raw_openf1', 'raw_openf1_sessions') }}
)

SELECT
    session_key,
    session_type,
    session_name,
    date_start::TIMESTAMP AS session_start_at,
    date_end::TIMESTAMP AS session_end_at,
    meeting_key,
    circuit_key,
    circuit_short_name,
    country_code,
    country_name,
    location,
    gmt_offset,
    year,
    is_cancelled,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
