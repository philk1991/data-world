-- Staged NBA franchise histories. One row per franchise era.
with source as (
    select * from {{ source('raw_nba', 'raw_nba_team_histories') }}
)

select
    teamId                              as team_id,
    teamCity                            as team_city,
    teamName                            as team_name,
    teamAbbrev                          as team_abbrev,
    seasonFounded                       as season_founded,
    seasonActiveTill                    as season_active_till,
    league,
    ingested_at::timestamp              as ingested_at
from source
