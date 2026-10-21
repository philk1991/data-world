-- One row per player aggregating their traditional box score totals and
-- averages across every game they appeared in, enriched with player bio.
-- Only games the player actually played (minutes_played is not null) count.
-- Made shots are only counted in games where the matching attempts were recorded,
-- so the shooting percentages compare like with like.
WITH box_scores AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics') }}
),

players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

career AS (
    SELECT
        person_id,
        COUNT(DISTINCT game_id) AS games_played,
        MIN(game_date) AS first_game_date,
        MAX(game_date) AS last_game_date,
        SUM(points) AS total_points,
        SUM(rebounds_total) AS total_rebounds,
        SUM(assists) AS total_assists,
        SUM(steals) AS total_steals,
        SUM(blocks) AS total_blocks,
        SUM(turnovers) AS total_turnovers,
        SUM(field_goals_made) FILTER (WHERE field_goals_attempted IS NOT NULL) AS total_field_goals_made,
        SUM(field_goals_attempted) AS total_field_goals_attempted,
        SUM(three_pointers_made) FILTER (WHERE three_pointers_attempted IS NOT NULL) AS total_three_pointers_made,
        SUM(three_pointers_attempted) AS total_three_pointers_attempted,
        SUM(free_throws_made) FILTER (WHERE free_throws_attempted IS NOT NULL) AS total_free_throws_made,
        SUM(free_throws_attempted) AS total_free_throws_attempted
    FROM
        box_scores
    WHERE
        person_id IS NOT NULL
        AND minutes_played IS NOT NULL
    GROUP BY
        person_id
),

career_rates AS (
    SELECT
        person_id,
        games_played,
        first_game_date,
        last_game_date,
        total_points,
        total_rebounds,
        total_assists,
        total_steals,
        total_blocks,
        total_turnovers,
        ROUND(total_points::DOUBLE / NULLIF(games_played, 0), 1) AS points_per_game,
        ROUND(total_rebounds::DOUBLE / NULLIF(games_played, 0), 1) AS rebounds_per_game,
        ROUND(total_assists::DOUBLE / NULLIF(games_played, 0), 1) AS assists_per_game,
        ROUND(
            total_field_goals_made::DOUBLE
            / NULLIF(total_field_goals_attempted, 0), 3
        ) AS career_field_goal_pct,
        ROUND(
            total_three_pointers_made::DOUBLE
            / NULLIF(total_three_pointers_attempted, 0), 3
        ) AS career_three_point_pct,
        ROUND(
            total_free_throws_made::DOUBLE
            / NULLIF(total_free_throws_attempted, 0), 3
        ) AS career_free_throw_pct
    FROM
        career
)

SELECT
    c.person_id,
    p.first_name,
    p.last_name,
    p.is_guard,
    p.is_forward,
    p.is_center,
    p.draft_year,
    p.height_inches,
    c.first_game_date,
    c.last_game_date,
    c.games_played,
    c.total_points,
    c.total_rebounds,
    c.total_assists,
    c.total_steals,
    c.total_blocks,
    c.total_turnovers,
    c.points_per_game,
    c.rebounds_per_game,
    c.assists_per_game,
    c.career_field_goal_pct,
    c.career_three_point_pct,
    c.career_free_throw_pct
FROM
    career_rates c
LEFT JOIN
    players p
    USING (person_id)
ORDER BY
    c.total_points DESC
