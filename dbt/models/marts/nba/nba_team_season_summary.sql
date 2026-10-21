-- One row per team per regular season with their win/loss record and scoring
-- averages. The NBA season spans two calendar years (Oct-Apr), so the season is
-- derived from the game date: months before July belong to the prior start year.
-- Restricted to Regular Season games so the record reflects the standings.
WITH team_box AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_statistics') }}
),

seasoned AS (
    SELECT
        team_id,
        CASE
            WHEN MONTH(game_date) >= 7 THEN YEAR(game_date)
            ELSE YEAR(game_date) - 1
        END AS season_start_year,
        is_win,
        is_home,
        team_score,
        opponent_score
    FROM
        team_box
    WHERE
        game_type = 'Regular Season'
),

team_season AS (
    SELECT
        team_id,
        season_start_year,
        COUNT(*) AS games_played,
        COUNT(CASE WHEN is_win THEN 1 END) AS wins,
        COUNT(CASE WHEN is_win = FALSE THEN 1 END) AS losses,
        COUNT(CASE WHEN is_home AND is_win THEN 1 END) AS home_wins,
        COUNT(CASE WHEN NOT is_home AND is_win THEN 1 END) AS away_wins,
        SUM(team_score) AS total_points_for,
        SUM(opponent_score) AS total_points_against
    FROM
        seasoned
    GROUP BY
        team_id, season_start_year
)

SELECT
    team_id,
    season_start_year,
    season_start_year::VARCHAR || '-'
    || RIGHT((season_start_year + 1)::VARCHAR, 2) AS season_label,
    games_played,
    wins,
    losses,
    home_wins,
    away_wins,
    ROUND(wins::DOUBLE / NULLIF(wins + losses, 0), 3) AS win_pct,
    ROUND(total_points_for::DOUBLE / NULLIF(games_played, 0), 1) AS points_for_per_game,
    ROUND(
        total_points_against::DOUBLE
        / NULLIF(games_played, 0), 1
    ) AS points_against_per_game,
    ROUND(
        (total_points_for - total_points_against)::DOUBLE
        / NULLIF(games_played, 0), 1
    ) AS point_margin_per_game
FROM
    team_season
ORDER BY
    season_start_year DESC, win_pct DESC
