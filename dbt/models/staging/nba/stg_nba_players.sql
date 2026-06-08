-- Staged NBA player biographies. Casts position/league flags to booleans.
with source as (
    select * from {{ source('raw_nba', 'raw_nba_players') }}
)

select
    personId                            as person_id,
    firstName                           as first_name,
    lastName                            as last_name,
    birthDate::date                     as birth_date,
    school,
    country,
    heightInches                        as height_inches,
    bodyWeightLbs                       as body_weight_lbs,
    jersey,
    guard = 1                           as is_guard,
    forward = 1                         as is_forward,
    center = 1                          as is_center,
    dleagueFlag = 1                     as is_dleague,
    nbaFlag = 1                         as is_nba,
    gamesPlayedFlag = 1                 as has_games_played,
    draftYear                           as draft_year,
    draftRound                          as draft_round,
    draftNumber                         as draft_number,
    fromYear                            as from_year,
    toYear                              as to_year,
    ingested_at::timestamp              as ingested_at
from source
