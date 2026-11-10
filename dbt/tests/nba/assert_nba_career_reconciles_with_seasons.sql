-- The career rollups equal the season rows they summarise: Regular Season and
-- Playoffs seasons from 1954-55 (nba_first_complete_season). Covers
-- nba_player_career_stats and the games and double-doubles of
-- nba_player_advanced_career. Returns each player and career scope that differs.
WITH season_stats AS (
    SELECT *
    FROM
        {{ ref('nba_player_season_stats') }}
),

game_stats AS (
    SELECT *
    FROM
        {{ ref('nba_player_game_stats') }}
),

career_stats AS (
    SELECT *
    FROM
        {{ ref('nba_player_career_stats') }}
),

advanced_career AS (
    SELECT *
    FROM
        {{ ref('nba_player_advanced_career') }}
),

seasons AS (
    SELECT
        person_id,
        game_type,
        SUM(games_played) AS games_played,
        SUM(total_points) AS total_points
    FROM
        season_stats
    WHERE
        game_type IN {{ nba_career_game_types() }}
        AND season_start_year >= {{ nba_first_complete_season() }}
    GROUP BY
        person_id, game_type
),

games AS (
    SELECT
        person_id,
        game_type,
        COUNT(*) FILTER (WHERE is_triple_double) AS triple_doubles
    FROM
        game_stats
    WHERE
        game_type IN {{ nba_career_game_types() }}
        AND season_start_year >= {{ nba_first_complete_season() }}
    GROUP BY
        person_id, game_type
)

SELECT
    s.person_id,
    s.game_type
FROM
    seasons s
LEFT JOIN
    career_stats c
    USING (person_id, game_type)
LEFT JOIN
    advanced_career a
    USING (person_id, game_type)
LEFT JOIN
    games g
    USING (person_id, game_type)
WHERE
    c.games_played IS DISTINCT FROM s.games_played
    OR c.total_points IS DISTINCT FROM s.total_points
    OR a.games_played IS DISTINCT FROM s.games_played
    OR a.triple_doubles IS DISTINCT FROM g.triple_doubles
