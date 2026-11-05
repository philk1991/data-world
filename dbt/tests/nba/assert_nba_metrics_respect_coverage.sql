-- No metric appears before its coverage start (possession metrics 1973-74,
-- three-point attempt rate 1979-80; player usage, turnover % and offensive
-- rating 1977-78, player steal/block % 1973-74, assist % 1964-65), and team rates
-- stay within possible ranges.
-- Returns each offending row with the rule it breaks.
WITH game_stats AS (
    SELECT *
    FROM
        {{ ref('nba_team_game_stats') }}
),

profile AS (
    SELECT *
    FROM
        {{ ref('nba_team_advanced_profile') }}
),

player_seasons AS (
    SELECT *
    FROM
        {{ ref('nba_player_season_advanced') }}
),

violations AS (
    SELECT
        'game: possession metric before 1973-74' AS rule,
        game_id::VARCHAR AS row_key
    FROM
        game_stats
    WHERE
        season_start_year < 1973
        AND (possessions IS NOT NULL OR offensive_rating IS NOT NULL OR pace IS NOT NULL)

    UNION ALL

    SELECT
        'game: three-point rate before 1979-80' AS rule,
        game_id::VARCHAR AS row_key
    FROM
        game_stats
    WHERE
        season_start_year < 1979
        AND three_point_attempt_rate IS NOT NULL

    UNION ALL

    SELECT
        'season: possession metric before 1973-74' AS rule,
        team_id::VARCHAR || '/' || season_start_year::VARCHAR AS row_key
    FROM
        profile
    WHERE
        season_start_year < 1973
        AND (offensive_rating IS NOT NULL OR pace IS NOT NULL OR turnover_pct IS NOT NULL)

    UNION ALL

    SELECT
        'season: rate outside 0-1 or pace outside 60-140' AS rule,
        team_id::VARCHAR || '/' || season_start_year::VARCHAR || '/' || game_type AS row_key
    FROM
        profile
    WHERE
        NOT (effective_field_goal_pct BETWEEN 0 AND 1)
        OR NOT (true_shooting_pct BETWEEN 0 AND 1)
        OR NOT (turnover_pct BETWEEN 0 AND 1)
        OR NOT (offensive_rebound_pct BETWEEN 0 AND 1)
        OR NOT (defensive_rebound_pct BETWEEN 0 AND 1)
        OR NOT (pace BETWEEN 60 AND 140)

    UNION ALL

    SELECT
        'player: metric before its coverage start' AS rule,
        person_id::VARCHAR || '/' || season_start_year::VARCHAR || '/' || game_type AS row_key
    FROM
        player_seasons
    WHERE
        (season_start_year < 1977 AND (
            usage_pct IS NOT NULL OR turnover_pct IS NOT NULL OR individual_offensive_rating IS NOT NULL
        ))
        OR (season_start_year < 1973 AND (steal_pct IS NOT NULL OR block_pct IS NOT NULL))
        OR (season_start_year < 1964 AND assist_pct IS NOT NULL)
)

SELECT *
FROM
    violations
