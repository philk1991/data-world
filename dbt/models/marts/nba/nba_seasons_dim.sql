-- Conformed season dimension: one row per season in the game records, with the
-- coverage facts every consumer filters on. coverage_tier is
-- incomplete_schedule before nba_first_complete_season (games against defunct
-- franchises are missing; plans/adr/0003-coverage-cutoff.md), in_progress for
-- the latest season, and complete otherwise. is_in_coverage is what careers,
-- Cube and nao's defaults filter on.
WITH games AS (
    SELECT *
    FROM
        {{ ref('stg_nba_games') }}
),

team_box AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_statistics') }}
),

-- Transform
team_regular_season AS (
    SELECT
        season_start_year,
        team_id,
        COUNT(DISTINCT game_id) AS games
    FROM
        team_box
    WHERE
        game_type = 'Regular Season'
    GROUP BY
        season_start_year, team_id
),

team_counts AS (
    SELECT
        season_start_year,
        COUNT(*) AS teams,
        MIN(games) AS min_team_regular_season_games,
        MAX(games) AS max_team_regular_season_games
    FROM
        team_regular_season
    GROUP BY
        season_start_year
),

seasons AS (
    SELECT
        season_start_year,
        MIN(game_date) AS season_first_game_date,
        MAX(game_date) AS season_last_game_date,
        COUNT(*) FILTER (WHERE game_type = 'Regular Season') AS regular_season_games,
        COUNT(*) FILTER (WHERE game_type = 'Playoffs') AS playoff_games
    FROM
        games
    GROUP BY
        season_start_year
)

SELECT
    s.season_start_year,
    {{ nba_season_label('s.season_start_year') }} AS season_label,
    s.season_first_game_date,
    s.season_last_game_date,
    s.regular_season_games,
    s.playoff_games,
    t.teams,
    t.min_team_regular_season_games,
    t.max_team_regular_season_games,
    s.season_start_year = MAX(s.season_start_year) OVER () AS is_current,
    CASE
        WHEN s.season_start_year < {{ nba_first_complete_season() }} THEN 'incomplete_schedule'
        WHEN s.season_start_year = MAX(s.season_start_year) OVER () THEN 'in_progress'
        ELSE 'complete'
    END AS coverage_tier,
    s.season_start_year >= {{ nba_first_complete_season() }} AS is_in_coverage
FROM
    seasons s
LEFT JOIN
    team_counts t
    USING (season_start_year)
ORDER BY
    s.season_start_year
