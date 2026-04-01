-- Staged StatsBomb competition/season pairs.
-- Minimal transformation: cast ingested_at and pass all columns through cleanly.
with source as (
    select * from {{ source('raw', 'raw_sb_competitions') }}
)

select
    competition_id,
    competition_name,
    country_name,
    competition_gender,
    competition_youth,
    competition_international,
    season_id,
    season_name,
    match_available_360,
    ingested_at::timestamp              as ingested_at
from source
