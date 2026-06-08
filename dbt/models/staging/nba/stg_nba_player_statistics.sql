-- Staged traditional player box scores. One row per player per game.
-- numMinutes is stored as text in the raw data and cast to a numeric value here.
with source as (
    select * from {{ source('raw_nba', 'raw_nba_player_statistics') }}
)

select
    gameId                              as game_id,
    personId                            as person_id,
    firstName                           as first_name,
    lastName                            as last_name,
    gameDate::date                      as game_date,
    gameDateTimeEst::timestamp          as game_datetime_est,
    gameType                            as game_type,
    gameLabel                           as game_label,
    gameSubLabel                        as game_sub_label,
    seriesGameNumber                    as series_game_number,
    playerteamId                        as player_team_id,
    playerteamCity                      as player_team_city,
    playerteamName                      as player_team_name,
    opponentteamId                      as opponent_team_id,
    opponentteamCity                    as opponent_team_city,
    opponentteamName                    as opponent_team_name,
    home = 1                            as is_home,
    win = 1                             as is_win,
    startingPosition                    as starting_position,
    comment,
    try_cast(numMinutes as double)      as minutes_played,
    points,
    assists,
    blocks,
    steals,
    fieldGoalsAttempted                 as field_goals_attempted,
    fieldGoalsMade                      as field_goals_made,
    fieldGoalsPercentage                as field_goals_percentage,
    threePointersAttempted              as three_pointers_attempted,
    threePointersMade                   as three_pointers_made,
    threePointersPercentage             as three_pointers_percentage,
    freeThrowsAttempted                 as free_throws_attempted,
    freeThrowsMade                      as free_throws_made,
    freeThrowsPercentage                as free_throws_percentage,
    reboundsOffensive                   as rebounds_offensive,
    reboundsDefensive                   as rebounds_defensive,
    reboundsTotal                       as rebounds_total,
    foulsPersonal                       as fouls_personal,
    turnovers,
    plusMinusPoints                     as plus_minus_points,
    ingested_at::timestamp              as ingested_at
from source
