-- One row per team per regular season summarising advanced efficiency metrics.
-- Sourced from the advanced team box scores (available since ~1996), so earlier
-- seasons are absent. Season comes from the game id, the same way as
-- nba_team_season_summary. Each regular-season game is a near-uniform number of
-- possessions, so per-game ratings are summarised with a simple mean.
WITH team_advanced AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_statistics_extended') }}
),

seasoned AS (
    SELECT
        team_id,
        season_start_year,
        offensive_rating,
        defensive_rating,
        net_rating,
        pace,
        effective_field_goal_percentage,
        true_shooting_percentage,
        assist_percentage,
        rebound_percentage,
        team_turnover_percentage,
        percent_field_goal_attempts_3_point,
        percent_points_in_paint,
        percent_points_fast_break
    FROM
        team_advanced
    WHERE
        game_type = 'Regular Season'
)

SELECT
    team_id,
    season_start_year,
    season_start_year::VARCHAR || '-'
    || RIGHT((season_start_year + 1)::VARCHAR, 2) AS season_label,
    COUNT(*) AS games_played,
    ROUND(AVG(offensive_rating), 1) AS offensive_rating,
    ROUND(AVG(defensive_rating), 1) AS defensive_rating,
    ROUND(AVG(net_rating), 1) AS net_rating,
    ROUND(AVG(pace), 1) AS pace,
    ROUND(AVG(effective_field_goal_percentage), 3) AS effective_field_goal_pct,
    ROUND(AVG(true_shooting_percentage), 3) AS true_shooting_pct,
    ROUND(AVG(assist_percentage), 3) AS assist_pct,
    ROUND(AVG(rebound_percentage), 3) AS rebound_pct,
    ROUND(AVG(team_turnover_percentage), 3) AS turnover_pct,
    ROUND(AVG(percent_field_goal_attempts_3_point), 3) AS three_point_attempt_rate,
    ROUND(AVG(percent_points_in_paint), 3) AS points_in_paint_share,
    ROUND(AVG(percent_points_fast_break), 3) AS fast_break_points_share
FROM
    seasoned
GROUP BY
    team_id, season_start_year
ORDER BY
    season_start_year DESC, net_rating DESC
