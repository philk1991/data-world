-- Staged NBA games. Renames/casts raw columns and derives home_team_won.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_nba', 'raw_nba_games') }}
)

SELECT
    gameId AS game_id,
    gameDateTimeEst::TIMESTAMP AS game_datetime_est,
    gameDate::DATE AS game_date,
    gameType AS game_type,
    gameSubtype AS game_subtype,
    gameLabel AS game_label,
    gameSubLabel AS game_sub_label,
    seriesGameNumber AS series_game_number,
    hometeamId AS home_team_id,
    hometeamCity AS home_team_city,
    hometeamName AS home_team_name,
    awayteamId AS away_team_id,
    awayteamCity AS away_team_city,
    awayteamName AS away_team_name,
    homeScore AS home_score,
    awayScore AS away_score,
    winner AS winner_team_id,
    winner = hometeamId AS home_team_won,
    attendance,
    arenaId AS arena_id,
    arenaName AS arena_name,
    arenaCity AS arena_city,
    arenaState AS arena_state,
    officials,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
