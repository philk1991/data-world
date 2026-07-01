with source as (
    select * from {{ source('raw_openf1', 'raw_openf1_sessions') }}
)

select
    session_key,
    session_type,
    session_name,
    date_start::timestamp                     as session_start_at,
    date_end::timestamp                       as session_end_at,
    meeting_key,
    circuit_key,
    circuit_short_name,
    country_code,
    country_name,
    location,
    gmt_offset,
    year,
    is_cancelled,
    ingested_at::timestamp                    as ingested_at
from source
