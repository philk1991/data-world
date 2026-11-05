-- As-of form must use only games before the as-of game: a team's window sizes
-- can never exceed the number of its earlier games that season and game type,
-- and the first game of a season and game type has no form at all.
WITH form AS (
    SELECT *
    FROM
        {{ ref('nba_team_form') }}
),

numbered AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY team_id, season_start_year, game_type ORDER BY game_date, game_id
        ) - 1 AS earlier_games
    FROM
        form
)

SELECT
    team_id,
    game_id,
    earlier_games,
    season_to_date_games,
    last_10_games,
    last_20_games
FROM
    numbered
WHERE
    season_to_date_games > earlier_games
    OR last_10_games > LEAST(earlier_games, 10)
    OR last_20_games > LEAST(earlier_games, 20)
    OR (earlier_games = 0 AND season_to_date_net_rating IS NOT NULL)
