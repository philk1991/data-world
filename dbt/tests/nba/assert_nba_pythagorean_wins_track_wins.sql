-- Pythagorean wins (exponent 14) should track actual wins: Basketball-Reference
-- reports an RMSE near 3.14 wins. Fails when the regular-season RMSE across
-- complete seasons (1983-84 to the last finished season) exceeds 4.
WITH profile AS (
    SELECT *
    FROM
        {{ ref('nba_team_advanced_profile') }}
),

current_season AS (
    SELECT MAX(season_start_year) AS season_start_year
    FROM
        profile
),

checks AS (
    SELECT SQRT(AVG(POWER(wins - pythagorean_wins, 2))) AS rmse
    FROM
        profile p
    CROSS JOIN
        current_season c
    WHERE
        p.game_type = 'Regular Season'
        AND p.season_start_year >= 1983
        AND p.season_start_year < c.season_start_year
)

SELECT *
FROM
    checks
WHERE
    rmse > 4
