-- One row per player per season and game type with any clutch-time event, from
-- the play-by-play (1996-97 on). Clutch time (int_nba_play_events) is the NBA's
-- definition: the last five minutes of the fourth quarter or any overtime, with
-- the score within five points, judged on the score before the event. Shooting
-- comes from nba_shot_events; games, rebounds and turnovers from the events.
-- The play-by-play has no record of who was on the floor, so a player's clutch
-- games are games with at least one clutch event of their own (a shot, free
-- throw, rebound, turnover or foul), not every game they were on court for one.
-- Assists, steals and blocks are left out: the legacy feed (to early 2019-20)
-- records assists only as names and steals and blocks not at all.
WITH play_events AS (
    SELECT *
    FROM
        {{ ref('int_nba_play_events') }}
),

shots AS (
    SELECT *
    FROM
        {{ ref('nba_shot_events') }}
),

box_scores AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics') }}
),

players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

-- Transform
box_score_names AS (
    SELECT
        person_id,
        ARG_MAX(first_name, game_date) AS first_name,
        ARG_MAX(last_name, game_date) AS last_name
    FROM
        box_scores
    GROUP BY
        person_id
),

-- Any clutch event of the player's own counts toward clutch games.
event_seasons AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        COUNT(DISTINCT game_id) FILTER (WHERE is_clutch) AS clutch_games,
        COUNT(*) FILTER (WHERE is_clutch AND event_type = 'rebound') AS clutch_rebounds,
        COUNT(*) FILTER (WHERE is_clutch AND event_type = 'turnover') AS clutch_turnovers
    FROM
        play_events
    GROUP BY
        person_id, season_start_year, game_type
),

shot_seasons AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        SUM(points_scored) FILTER (WHERE is_clutch) AS clutch_points,
        COUNT(*) FILTER (WHERE is_clutch AND shot_type = 'field_goal') AS clutch_field_goals_attempted,
        COUNT(*) FILTER (WHERE is_clutch AND shot_type = 'field_goal' AND is_shot_made) AS clutch_field_goals_made,
        COUNT(*) FILTER (
            WHERE is_clutch AND shot_type = 'field_goal' AND shot_value = 3
        ) AS clutch_three_pointers_attempted,
        COUNT(*) FILTER (
            WHERE is_clutch AND shot_type = 'field_goal' AND shot_value = 3 AND is_shot_made
        ) AS clutch_three_pointers_made,
        COUNT(*) FILTER (WHERE is_clutch AND shot_type = 'free_throw') AS clutch_free_throws_attempted,
        COUNT(*) FILTER (WHERE is_clutch AND shot_type = 'free_throw' AND is_shot_made) AS clutch_free_throws_made,
        COUNT(*) FILTER (WHERE is_clutch AND is_go_ahead) AS clutch_go_ahead_field_goals,
        -- Every-minute shooting from the same events, as the baseline to compare against.
        SUM(points_scored) AS points,
        COUNT(*) FILTER (WHERE shot_type = 'field_goal') AS field_goals_attempted,
        COUNT(*) FILTER (WHERE shot_type = 'free_throw') AS free_throws_attempted
    FROM
        shots
    GROUP BY
        person_id, season_start_year, game_type
),

player_seasons AS (
    SELECT
        e.*,
        COALESCE(s.clutch_points, 0) AS clutch_points,
        COALESCE(s.clutch_field_goals_attempted, 0) AS clutch_field_goals_attempted,
        COALESCE(s.clutch_field_goals_made, 0) AS clutch_field_goals_made,
        COALESCE(s.clutch_three_pointers_attempted, 0) AS clutch_three_pointers_attempted,
        COALESCE(s.clutch_three_pointers_made, 0) AS clutch_three_pointers_made,
        COALESCE(s.clutch_free_throws_attempted, 0) AS clutch_free_throws_attempted,
        COALESCE(s.clutch_free_throws_made, 0) AS clutch_free_throws_made,
        COALESCE(s.clutch_go_ahead_field_goals, 0) AS clutch_go_ahead_field_goals,
        s.points,
        s.field_goals_attempted,
        s.free_throws_attempted
    FROM
        event_seasons e
    LEFT JOIN
        shot_seasons s
        USING (person_id, season_start_year, game_type)
),

enriched AS (
    SELECT
        ps.person_id,
        COALESCE(p.first_name, n.first_name) AS first_name,
        COALESCE(p.last_name, n.last_name) AS last_name,
        ps.season_start_year,
        {{ nba_season_label('ps.season_start_year') }} AS season_label,
        ps.game_type,
        ps.clutch_games,
        ps.clutch_points,
        ps.clutch_points / ps.clutch_games AS clutch_points_per_game,
        ps.clutch_field_goals_made,
        ps.clutch_field_goals_attempted,
        ps.clutch_field_goals_made / NULLIF(ps.clutch_field_goals_attempted, 0) AS clutch_field_goal_pct,
        ps.clutch_three_pointers_made,
        ps.clutch_three_pointers_attempted,
        ps.clutch_three_pointers_made / NULLIF(ps.clutch_three_pointers_attempted, 0) AS clutch_three_point_pct,
        ps.clutch_free_throws_made,
        ps.clutch_free_throws_attempted,
        ps.clutch_free_throws_made / NULLIF(ps.clutch_free_throws_attempted, 0) AS clutch_free_throw_pct,
        {{ nba_ts('ps.clutch_points', 'ps.clutch_field_goals_attempted', 'ps.clutch_free_throws_attempted') }}
            AS clutch_true_shooting_pct,
        {{ nba_ts('ps.points', 'ps.field_goals_attempted', 'ps.free_throws_attempted') }} AS true_shooting_pct,
        ps.clutch_rebounds,
        ps.clutch_turnovers,
        ps.clutch_go_ahead_field_goals
    FROM
        player_seasons ps
    LEFT JOIN
        players p
        USING (person_id)
    LEFT JOIN
        box_score_names n
        USING (person_id)
    WHERE
        ps.clutch_games > 0
)

SELECT *
FROM
    enriched
ORDER BY
    season_start_year DESC, game_type ASC, clutch_points DESC
