-- Conformed game type dimension: one row per game type decoded from the game id
-- (macros/nba_game_id.sql), with the scope flags consumers filter on:
-- is_competitive (macros/nba_scope.sql) and is_career, the types a career is
-- reported for (plans/adr/0001-career-scope.md).
WITH game_types AS (
    SELECT *
    FROM
        (
            VALUES
            (1, 'Preseason', FALSE),
            (2, 'Regular Season', TRUE),
            (3, 'All-Star Game', FALSE),
            (4, 'Playoffs', FALSE),
            (5, 'Play-in Tournament', FALSE),
            (6, 'NBA Cup Final', FALSE)
        ) AS t (game_type_code, game_type, counts_toward_standings)  -- noqa: AL01, AL05
)

SELECT
    game_type_code,
    game_type,
    game_type IN {{ nba_competitive_game_types() }} AS is_competitive,
    game_type IN {{ nba_career_game_types() }} AS is_career,
    counts_toward_standings
FROM
    game_types
ORDER BY
    game_type_code
