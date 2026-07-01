with source as (
    select * from {{ source('raw_openf1', 'raw_openf1_meetings') }}
)

select
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
    date_start::timestamp                     as meeting_start_at,
    date_end::timestamp                       as meeting_end_at,
    year,
    is_cancelled,
    ingested_at::timestamp                    as ingested_at
from source
