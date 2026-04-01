-- Staged StatsBomb lineup data. One row per player per match.
with source as (
    select * from {{ source('raw', 'raw_sb_lineups') }}
)

select
    match_id,
    team_name,
    player_id,
    player_name,
    player_nickname,
    jersey_number,
    country_name,
    ingested_at::timestamp              as ingested_at
from source
