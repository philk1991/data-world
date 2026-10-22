-- Staged traditional player box scores. One row per player per game.
-- game_type and season_start_year are decoded from the game id (see macros/nba_game_id.sql).
-- numMinutes is stored as text in the raw data and cast to a numeric value here.
-- Box score stats the league did not record yet are zero-filled in the raw data;
-- null_if_unrecorded turns them back into nulls (see the macro).
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
    {{ nba_game_type('gameId') }} AS game_type,
    {{ nba_season_start_year('gameId') }} AS season_start_year,
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
    {{ null_if_unrecorded('assists') }} AS assists,
    {{ null_if_unrecorded('blocks') }} AS blocks,
    {{ null_if_unrecorded('steals') }} AS steals,
    {{
        null_if_unrecorded('fieldGoalsAttempted', attempts='fieldGoalsAttempted', made='fieldGoalsMade')
    }} AS field_goals_attempted,
    {{ null_if_unrecorded('fieldGoalsMade') }} AS field_goals_made,
    {{
        null_if_unrecorded(
            'fieldGoalsPercentage', signal='fieldGoalsAttempted',
            attempts='fieldGoalsAttempted', made='fieldGoalsMade'
        )
    }} AS field_goals_percentage,
    {{
        null_if_unrecorded('threePointersAttempted', attempts='threePointersAttempted', made='threePointersMade')
    }} AS three_pointers_attempted,
    {{
        null_if_unrecorded('threePointersMade', signal='threePointersAttempted + threePointersMade')
    }} AS three_pointers_made,
    {{
        null_if_unrecorded(
            'threePointersPercentage', signal='threePointersAttempted',
            attempts='threePointersAttempted', made='threePointersMade'
        )
    }} AS three_pointers_percentage,
    {{
        null_if_unrecorded('freeThrowsAttempted', attempts='freeThrowsAttempted', made='freeThrowsMade')
    }} AS free_throws_attempted,
    {{ null_if_unrecorded('freeThrowsMade') }} AS free_throws_made,
    {{
        null_if_unrecorded(
            'freeThrowsPercentage', signal='freeThrowsAttempted',
            attempts='freeThrowsAttempted', made='freeThrowsMade'
        )
    }} AS free_throws_percentage,
    {{ null_if_unrecorded('reboundsOffensive') }} AS rebounds_offensive,
    {{ null_if_unrecorded('reboundsDefensive') }} AS rebounds_defensive,
    {{ null_if_unrecorded('reboundsTotal') }} AS rebounds_total,
    {{ null_if_unrecorded('foulsPersonal') }} AS fouls_personal,
    {{ null_if_unrecorded('turnovers') }} AS turnovers,
    plusMinusPoints AS plus_minus_points,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
