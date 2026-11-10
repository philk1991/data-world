-- No player row anywhere records more makes than attempts, so no shooting
-- percentage can pass 1. int_nba_player_games nulls impossible pairs; this
-- guards every player mart built on it. Returns each offending row.
WITH game_stats AS (
    SELECT *
    FROM
        {{ ref('nba_player_game_stats') }}
),

season_stats AS (
    SELECT *
    FROM
        {{ ref('nba_player_season_stats') }}
),

career_stats AS (
    SELECT *
    FROM
        {{ ref('nba_player_career_stats') }}
)

SELECT
    'game' AS grain,
    person_id::VARCHAR || '/' || game_id::VARCHAR AS row_key
FROM
    game_stats
WHERE
    field_goals_made > field_goals_attempted
    OR three_pointers_made > three_pointers_attempted
    OR free_throws_made > free_throws_attempted

UNION ALL

SELECT
    'season' AS grain,
    person_id::VARCHAR || '/' || season_start_year::VARCHAR || '/' || game_type AS row_key
FROM
    season_stats
WHERE
    total_field_goals_made > total_field_goals_attempted
    OR total_three_pointers_made > total_three_pointers_attempted
    OR total_free_throws_made > total_free_throws_attempted
    OR ts_points < 0

UNION ALL

SELECT
    'career' AS grain,
    person_id::VARCHAR || '/' || game_type AS row_key
FROM
    career_stats
WHERE
    total_field_goals_made > total_field_goals_attempted
    OR total_three_pointers_made > total_three_pointers_attempted
    OR total_free_throws_made > total_free_throws_attempted
