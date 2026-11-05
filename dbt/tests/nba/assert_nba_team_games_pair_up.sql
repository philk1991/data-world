-- Every competitive game has exactly two team rows, and each side's points equal
-- the other side's opp_points. Returns each game that breaks either rule.
WITH team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
)

SELECT
    game_id,
    COUNT(*) AS team_rows,
    SUM(points) AS points,
    SUM(opp_points) AS opp_points
FROM
    team_games
GROUP BY
    game_id
HAVING
    COUNT(*) <> 2
    OR SUM(points) <> SUM(opp_points)
