-- Staged traditional player box scores. One row per player per game.
-- numMinutes is stored as text in the raw data and cast to a numeric value here.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_nba', 'raw_nba_player_statistics') }}
)

SELECT
    gameId AS game_id,
    personId AS person_id,
    firstName AS first_name,
    lastName AS last_name,
    gameDate::DATE AS game_date,
    gameDateTimeEst::TIMESTAMP AS game_datetime_est,
    gameType AS game_type,
    gameLabel AS game_label,
    gameSubLabel AS game_sub_label,
    seriesGameNumber AS series_game_number,
    playerteamId AS player_team_id,
    playerteamCity AS player_team_city,
    playerteamName AS player_team_name,
    opponentteamId AS opponent_team_id,
    opponentteamCity AS opponent_team_city,
    opponentteamName AS opponent_team_name,
    home = 1 AS is_home,
    win = 1 AS is_win,
    startingPosition AS starting_position,
    comment,
    TRY_CAST(numMinutes AS DOUBLE) AS minutes_played,
    points,
    assists,
    blocks,
    steals,
    fieldGoalsAttempted AS field_goals_attempted,
    fieldGoalsMade AS field_goals_made,
    fieldGoalsPercentage AS field_goals_percentage,
    threePointersAttempted AS three_pointers_attempted,
    threePointersMade AS three_pointers_made,
    threePointersPercentage AS three_pointers_percentage,
    freeThrowsAttempted AS free_throws_attempted,
    freeThrowsMade AS free_throws_made,
    freeThrowsPercentage AS free_throws_percentage,
    reboundsOffensive AS rebounds_offensive,
    reboundsDefensive AS rebounds_defensive,
    reboundsTotal AS rebounds_total,
    foulsPersonal AS fouls_personal,
    turnovers,
    plusMinusPoints AS plus_minus_points,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
