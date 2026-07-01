with source as (
    select * from {{ source('raw_openf1', 'raw_openf1_drivers') }}
)

select
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
    ingested_at::timestamp                    as ingested_at
from source
