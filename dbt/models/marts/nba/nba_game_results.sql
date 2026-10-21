-- One row per game combining game metadata with both teams' box score lines.
-- Team box scores are pivoted onto the home/away axis via conditional aggregation.
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

game_team_stats AS (
    SELECT
        game_id,
        MAX(CASE WHEN is_home THEN field_goals_made END) AS home_field_goals_made,
        MAX(CASE WHEN is_home THEN field_goals_attempted END) AS home_field_goals_attempted,
        MAX(CASE WHEN is_home THEN three_pointers_made END) AS home_three_pointers_made,
        MAX(CASE WHEN is_home THEN rebounds_total END) AS home_rebounds_total,
        MAX(CASE WHEN is_home THEN assists END) AS home_assists,
        MAX(CASE WHEN is_home THEN turnovers END) AS home_turnovers,
        MAX(CASE WHEN is_home THEN points_in_the_paint END) AS home_points_in_the_paint,
        MAX(CASE WHEN NOT is_home THEN field_goals_made END) AS away_field_goals_made,
        MAX(CASE WHEN NOT is_home THEN field_goals_attempted END) AS away_field_goals_attempted,
        MAX(CASE WHEN NOT is_home THEN three_pointers_made END) AS away_three_pointers_made,
        MAX(CASE WHEN NOT is_home THEN rebounds_total END) AS away_rebounds_total,
        MAX(CASE WHEN NOT is_home THEN assists END) AS away_assists,
        MAX(CASE WHEN NOT is_home THEN turnovers END) AS away_turnovers,
        MAX(CASE WHEN NOT is_home THEN points_in_the_paint END) AS away_points_in_the_paint
    FROM
        team_box
    GROUP BY
        game_id
)

SELECT
    g.game_id,
    g.game_date,
    g.game_datetime_est,
    g.game_type,
    g.home_team_id,
    g.home_team_name,
    g.away_team_id,
    g.away_team_name,
    g.home_score,
    g.away_score,
    g.home_score - g.away_score AS point_margin,
    g.home_team_won,
    g.attendance,
    g.arena_name,
    s.home_field_goals_made,
    s.home_field_goals_attempted,
    s.home_three_pointers_made,
    s.home_rebounds_total,
    s.home_assists,
    s.home_turnovers,
    s.home_points_in_the_paint,
    s.away_field_goals_made,
    s.away_field_goals_attempted,
    s.away_three_pointers_made,
    s.away_rebounds_total,
    s.away_assists,
    s.away_turnovers,
    s.away_points_in_the_paint,
    g.ingested_at
FROM
    games g
LEFT JOIN
    game_team_stats s
    USING (game_id)
ORDER BY
    g.game_date DESC
