WITH source AS (
    SELECT *
    FROM
        {{ source('raw_openf1', 'raw_openf1_meetings') }}
)

SELECT
    meeting_key,
    meeting_name,
    meeting_official_name,
    location,
    country_key,
    country_code,
    country_name,
    circuit_key,
    circuit_short_name,
    gmt_offset,
    date_start::TIMESTAMP AS meeting_start_at,
    date_end::TIMESTAMP AS meeting_end_at,
    year,
    is_cancelled,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
