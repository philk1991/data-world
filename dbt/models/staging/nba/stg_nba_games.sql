-- Staged NBA games. Renames/casts raw columns and derives home_team_won.
with source as (
    select * from {{ source('raw_nba', 'raw_nba_games') }}
)

select
    gameId                              as game_id,
    gameDateTimeEst::timestamp          as game_datetime_est,
    gameDate::date                      as game_date,
    gameType                            as game_type,
    gameSubtype                         as game_subtype,
    gameLabel                           as game_label,
    gameSubLabel                        as game_sub_label,
    seriesGameNumber                    as series_game_number,
    hometeamId                          as home_team_id,
    hometeamCity                        as home_team_city,
    hometeamName                        as home_team_name,
    awayteamId                          as away_team_id,
    awayteamCity                        as away_team_city,
    awayteamName                        as away_team_name,
    homeScore                           as home_score,
    awayScore                           as away_score,
    winner                              as winner_team_id,
    winner = hometeamId                 as home_team_won,
    attendance,
    arenaId                             as arena_id,
    arenaName                           as arena_name,
    arenaCity                           as arena_city,
    arenaState                          as arena_state,
    officials,
    ingested_at::timestamp              as ingested_at
from source
