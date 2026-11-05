-- Team player-minutes should be 240 for a regulation game plus 25 per overtime.
-- A handful of 1960s box scores are a minute or two off, so this fails only
-- when more than 0.1% of team games with recorded minutes break the rule.
WITH team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

checks AS (
    SELECT AVG((team_minutes <> 240 + 25 * overtime_periods)::INTEGER) AS mismatch_rate
    FROM
        team_games
    WHERE
        team_minutes IS NOT NULL
)

SELECT *
FROM
    checks
WHERE
    mismatch_rate > 0.001
