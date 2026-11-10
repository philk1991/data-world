-- Every game in the marts has a result: both sides scored. Catches games the
-- source records 0-0 with no box score (two in 2024-25, dropped in staging).
-- Returns each offending game with the mart it came from.
WITH game_results AS (
    SELECT *
    FROM
        {{ ref('nba_game_results') }}
),

team_games AS (
    SELECT *
    FROM
        {{ ref('nba_team_game_stats') }}
)

SELECT
    'nba_game_results' AS mart,
    game_id
FROM
    game_results
WHERE
    COALESCE(home_score, 0) <= 0
    OR COALESCE(away_score, 0) <= 0

UNION ALL

SELECT
    'nba_team_game_stats' AS mart,
    game_id
FROM
    team_games
WHERE
    COALESCE(points, 0) <= 0
    OR COALESCE(opp_points, 0) <= 0
