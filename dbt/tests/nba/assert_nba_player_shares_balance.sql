-- Five players share the floor, so across a complete season the minute-weighted
-- league usage must be 0.2 and the minute-weighted total rebound share 0.1.
-- Checked per regular season from 1983-84 (complete box scores); fails when
-- either is more than 0.005 off.
WITH season_advanced AS (
    SELECT *
    FROM
        {{ ref('nba_player_season_advanced') }}
),

checks AS (
    SELECT
        season_start_year,
        SUM(usage_pct * total_minutes) / SUM(total_minutes) FILTER (WHERE usage_pct IS NOT NULL) AS usage_mean,
        SUM(rebound_pct * total_minutes) / SUM(total_minutes) FILTER (WHERE rebound_pct IS NOT NULL) AS rebound_mean
    FROM
        season_advanced
    WHERE
        game_type = 'Regular Season'
        AND season_start_year >= 1983
    GROUP BY
        season_start_year
)

SELECT *
FROM
    checks
WHERE
    ABS(usage_mean - 0.2) > 0.005
    OR ABS(rebound_mean - 0.1) > 0.005
