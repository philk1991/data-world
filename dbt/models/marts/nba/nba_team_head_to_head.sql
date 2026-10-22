-- All-time matchup record, one row per ordered (team_id, opponent_team_id) pair.
-- Each game contributes one team-perspective row in the source, so a team's row
-- against an opponent is its record directly; the reverse matchup is a separate
-- row. Restricted to competitive meetings (Regular Season, Playoffs, Play-in
-- Tournament and NBA Cup Final) to exclude preseason and All-Star exhibitions.
-- Join nba_team_dim on either id for team names.
WITH team_box AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_statistics') }}
),

matchups AS (
    SELECT
        team_id,
        opponent_team_id,
        game_id,
        game_date,
        is_win,
        team_score,
        opponent_score
    FROM
        team_box
    WHERE
        game_type IN ('Regular Season', 'Playoffs', 'Play-in Tournament', 'NBA Cup Final')
        AND opponent_team_id IS NOT NULL
)

SELECT
    team_id,
    opponent_team_id,
    COUNT(DISTINCT game_id) AS games_played,
    COUNT(CASE WHEN is_win THEN 1 END) AS wins,
    COUNT(CASE WHEN is_win = FALSE THEN 1 END) AS losses,
    ROUND(
        COUNT(CASE WHEN is_win THEN 1 END)::DOUBLE
        / NULLIF(COUNT(CASE WHEN is_win IS NOT NULL THEN 1 END), 0), 3
    ) AS win_pct,
    ROUND(AVG(team_score), 1) AS avg_points_for,
    ROUND(AVG(opponent_score), 1) AS avg_points_against,
    ROUND(AVG(team_score - opponent_score), 1) AS avg_point_margin,
    MIN(game_date) AS first_meeting_date,
    MAX(game_date) AS last_meeting_date
FROM
    matchups
GROUP BY
    team_id, opponent_team_id
ORDER BY
    games_played DESC
