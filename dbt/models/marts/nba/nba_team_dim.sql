-- Conformed franchise dimension: one row per team_id carrying its current
-- identity, with relocation/rename history rolled up from the franchise eras.
-- stg_nba_team_histories holds one row per franchise era (team_id, season_founded);
-- the window aggregates run over every era, then QUALIFY keeps the latest one.
with histories as (
    select * from {{ ref('stg_nba_team_histories') }}
)

select
    team_id,
    team_city                                                       as current_team_city,
    team_name                                                       as current_team_name,
    team_city || ' ' || team_name                                  as current_full_name,
    team_abbrev                                                     as current_team_abbrev,
    league                                                          as current_league,
    season_founded                                                  as current_era_season_founded,
    season_active_till                                              as current_era_active_till,
    min(season_founded) over (partition by team_id)                as franchise_first_season,
    count(*) over (partition by team_id)                           as franchise_era_count,
    count(*) over (partition by team_id) > 1                        as has_relocated_or_renamed
from histories
qualify row_number() over (partition by team_id order by season_founded desc) = 1
order by team_id
