-- Staged StatsBomb match metadata.
-- Derives match_result and goal_difference. Filters to available matches only.
with source as (
    select * from {{ source('raw', 'raw_sb_matches') }}
)

select
    match_id,
    match_date::date                    as match_date,
    kick_off::time                      as kick_off,
    competition_id,
    competition_name,
    season_id,
    season_name,
    home_team_id,
    home_team_name,
    away_team_id,
    away_team_name,
    home_score,
    away_score,
    home_score - away_score             as goal_difference,
    case
        when home_score > away_score    then 'home_win'
        when home_score < away_score    then 'away_win'
        else                                 'draw'
    end                                 as match_result,
    match_status,
    match_week,
    competition_stage,
    stadium_name,
    referee_name,
    ingested_at::timestamp              as ingested_at
from source
where match_status = 'available'
