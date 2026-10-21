-- One row per player per season per game type (Regular Season, Playoffs, etc.)
-- of traditional box score totals, per-game averages and shooting splits,
-- enriched with bio. Season is derived from the game date (months before July
-- belong to the prior start year). A player traded mid-season is combined into a
-- single row per game type; primary_team_id is the team they played the most
-- games for. Only games actually played (minutes_played not null) count.
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

seasoned AS (
    SELECT
        person_id,
        CASE
            WHEN MONTH(game_date) >= 7 THEN YEAR(game_date)
            ELSE YEAR(game_date) - 1
        END AS season_start_year,
        game_type,
        player_team_id,
        game_id,
        points,
        rebounds_total,
        assists,
        steals,
        blocks,
        turnovers,
        field_goals_made,
        field_goals_attempted,
        three_pointers_made,
        three_pointers_attempted,
        free_throws_made,
        free_throws_attempted
    FROM
        box_scores
    WHERE
        person_id IS NOT NULL
        AND minutes_played IS NOT NULL
        AND game_date IS NOT NULL
        AND game_type IS NOT NULL
),

season_totals AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        MODE(player_team_id) AS primary_team_id,
        COUNT(DISTINCT game_id) AS games_played,
        SUM(points) AS total_points,
        SUM(rebounds_total) AS total_rebounds,
        SUM(assists) AS total_assists,
        SUM(steals) AS total_steals,
        SUM(blocks) AS total_blocks,
        SUM(turnovers) AS total_turnovers,
        SUM(field_goals_made) AS total_field_goals_made,
        SUM(field_goals_attempted) AS total_field_goals_attempted,
        SUM(three_pointers_made) AS total_three_pointers_made,
        SUM(three_pointers_attempted) AS total_three_pointers_attempted,
        SUM(free_throws_made) AS total_free_throws_made,
        SUM(free_throws_attempted) AS total_free_throws_attempted
    FROM
        seasoned
    GROUP BY
        person_id, season_start_year, game_type
)

SELECT
    s.person_id,
    p.first_name,
    p.last_name,
    s.season_start_year,
    s.season_start_year::VARCHAR || '-'
    || RIGHT((s.season_start_year + 1)::VARCHAR, 2) AS season_label,
    s.game_type,
    s.primary_team_id,
    s.games_played,
    s.total_points,
    s.total_rebounds,
    s.total_assists,
    s.total_steals,
    s.total_blocks,
    s.total_turnovers,
    ROUND(s.total_points::DOUBLE / NULLIF(s.games_played, 0), 1) AS points_per_game,
    ROUND(s.total_rebounds::DOUBLE / NULLIF(s.games_played, 0), 1) AS rebounds_per_game,
    ROUND(s.total_assists::DOUBLE / NULLIF(s.games_played, 0), 1) AS assists_per_game,
    ROUND(
        s.total_field_goals_made::DOUBLE
        / NULLIF(s.total_field_goals_attempted, 0), 3
    ) AS field_goal_pct,
    ROUND(
        s.total_three_pointers_made::DOUBLE
        / NULLIF(s.total_three_pointers_attempted, 0), 3
    ) AS three_point_pct,
    ROUND(
        s.total_free_throws_made::DOUBLE
        / NULLIF(s.total_free_throws_attempted, 0), 3
    ) AS free_throw_pct
FROM
    season_totals s
LEFT JOIN
    players p
    USING (person_id)
ORDER BY
    s.season_start_year DESC, s.total_points DESC
