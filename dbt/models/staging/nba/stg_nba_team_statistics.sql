-- Staged traditional team box scores. One row per team per game.
-- Box score stats the league did not record yet are zero-filled in the raw data;
-- null_if_unrecorded turns them back into nulls (see the macro).
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_nba', 'raw_nba_team_statistics') }}
)

SELECT
    gameId AS game_id,
    teamId AS team_id,
    teamCity AS team_city,
    teamName AS team_name,
    opponentTeamId AS opponent_team_id,
    opponentTeamCity AS opponent_team_city,
    opponentTeamName AS opponent_team_name,
    gameDate::DATE AS game_date,
    gameDateTimeEst::TIMESTAMP AS game_datetime_est,
    gameType AS game_type,
    gameLabel AS game_label,
    gameSubLabel AS game_sub_label,
    seriesGameNumber AS series_game_number,
    seed,
    coachId AS coach_id,
    home = 1 AS is_home,
    win = 1 AS is_win,
    teamScore AS team_score,
    opponentScore AS opponent_score,
    numMinutes AS minutes_played,
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
    {{ null_if_unrecorded('reboundsTeam') }} AS rebounds_team,
    {{ null_if_unrecorded('foulsPersonal') }} AS fouls_personal,
    {{ null_if_unrecorded('turnovers') }} AS turnovers,
    {{ null_if_unrecorded('turnoversTeam') }} AS turnovers_team,
    plusMinusPoints AS plus_minus_points,
    q1Points AS q1_points,
    q2Points AS q2_points,
    q3Points AS q3_points,
    q4Points AS q4_points,
    ot1Points AS ot1_points,
    ot2Points AS ot2_points,
    otAllPoints AS ot_all_points,
    {{ null_if_unrecorded('benchPoints') }} AS bench_points,
    biggestLead AS biggest_lead,
    biggestScoringRun AS biggest_scoring_run,
    leadChanges AS lead_changes,
    {{ null_if_unrecorded('pointsFastBreak') }} AS points_fast_break,
    {{ null_if_unrecorded('pointsFromTurnovers') }} AS points_from_turnovers,
    {{ null_if_unrecorded('pointsInThePaint') }} AS points_in_the_paint,
    {{ null_if_unrecorded('pointsSecondChance') }} AS points_second_chance,
    timesTied AS times_tied,
    timeoutsRemaining AS timeouts_remaining,
    seasonWins AS season_wins,
    seasonLosses AS season_losses,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
