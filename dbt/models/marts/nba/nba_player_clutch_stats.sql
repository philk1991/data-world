-- One row per player per season and game type with any clutch-time event, from
-- the play-by-play (1996-97 on). Clutch time is the NBA's definition: the last
-- five minutes of the fourth quarter or any overtime, with the score within five
-- points. Whether an event is clutch is judged on the score before it, so the
-- shot that opens a six-point lead still counts.
-- The play-by-play has no record of who was on the floor, so a player's clutch
-- games are games with at least one clutch event of their own (a shot, free
-- throw, rebound, turnover or foul), not every game they were on court for one.
-- Assists, steals and blocks are left out: the legacy feed (to early 2019-20)
-- records assists only as names and steals and blocks not at all.
WITH play_by_play AS (
    SELECT *
    FROM
        {{ ref('stg_nba_play_by_play') }}
),

games AS (
    SELECT *
    FROM
        {{ ref('stg_nba_games') }}
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

events AS (
    SELECT
        pbp.*,
        pbp.team_id = g.home_team_id AS is_home,
        -- Score before the event: the previous event's score.
        COALESCE(LAG(pbp.score_home) OVER game_order, 0) AS score_home_before,
        COALESCE(LAG(pbp.score_away) OVER game_order, 0) AS score_away_before
    FROM
        play_by_play pbp
    LEFT JOIN
        games g
        USING (game_id)
    WINDOW game_order AS (PARTITION BY pbp.game_id ORDER BY pbp.event_order)
),

player_events AS (
    SELECT
        *,
        period >= 4
        AND clock_seconds_remaining <= 300
        AND ABS(score_home_before - score_away_before) <= 5 AS is_clutch,
        -- Null for the few games missing from the game records, so they never count as go-ahead.
        CASE
            WHEN is_home THEN score_home_before - score_away_before
            WHEN NOT is_home THEN score_away_before - score_home_before
        END AS team_margin_before
    FROM
        events
    WHERE
        person_id IS NOT NULL
),

player_seasons AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        COUNT(DISTINCT game_id) FILTER (WHERE is_clutch) AS clutch_games,
        SUM(points_scored) FILTER (WHERE is_clutch) AS clutch_points,
        COUNT(*) FILTER (WHERE is_clutch AND event_type = 'field_goal') AS clutch_field_goals_attempted,
        COUNT(*) FILTER (WHERE is_clutch AND event_type = 'field_goal' AND is_shot_made) AS clutch_field_goals_made,
        COUNT(*) FILTER (
            WHERE is_clutch AND event_type = 'field_goal' AND shot_value = 3
        ) AS clutch_three_pointers_attempted,
        COUNT(*) FILTER (
            WHERE is_clutch AND event_type = 'field_goal' AND shot_value = 3 AND is_shot_made
        ) AS clutch_three_pointers_made,
        COUNT(*) FILTER (WHERE is_clutch AND event_type = 'free_throw') AS clutch_free_throws_attempted,
        COUNT(*) FILTER (WHERE is_clutch AND event_type = 'free_throw' AND is_shot_made) AS clutch_free_throws_made,
        COUNT(*) FILTER (WHERE is_clutch AND event_type = 'rebound') AS clutch_rebounds,
        COUNT(*) FILTER (WHERE is_clutch AND event_type = 'turnover') AS clutch_turnovers,
        -- A made field goal that took the team from tied or behind to ahead.
        COUNT(*) FILTER (
            WHERE is_clutch AND event_type = 'field_goal' AND is_shot_made
            AND team_margin_before <= 0 AND team_margin_before + points_scored > 0
        ) AS clutch_go_ahead_field_goals,
        -- Every-minute shooting from the same events, as the baseline to compare against.
        SUM(points_scored) AS points,
        COUNT(*) FILTER (WHERE event_type = 'field_goal') AS field_goals_attempted,
        COUNT(*) FILTER (WHERE event_type = 'free_throw') AS free_throws_attempted
    FROM
        player_events
    GROUP BY
        person_id, season_start_year, game_type
),

enriched AS (
    SELECT
        ps.person_id,
        COALESCE(p.first_name, n.first_name) AS first_name,
        COALESCE(p.last_name, n.last_name) AS last_name,
        ps.season_start_year,
        ps.season_start_year::VARCHAR || '-'
        || RIGHT((ps.season_start_year + 1)::VARCHAR, 2) AS season_label,
        ps.game_type,
        ps.clutch_games,
        ps.clutch_points,
        ROUND(ps.clutch_points / ps.clutch_games, 2) AS clutch_points_per_game,
        ps.clutch_field_goals_made,
        ps.clutch_field_goals_attempted,
        ROUND(ps.clutch_field_goals_made / NULLIF(ps.clutch_field_goals_attempted, 0), 3) AS clutch_field_goal_pct,
        ps.clutch_three_pointers_made,
        ps.clutch_three_pointers_attempted,
        ROUND(
            ps.clutch_three_pointers_made / NULLIF(ps.clutch_three_pointers_attempted, 0), 3
        ) AS clutch_three_point_pct,
        ps.clutch_free_throws_made,
        ps.clutch_free_throws_attempted,
        ROUND(ps.clutch_free_throws_made / NULLIF(ps.clutch_free_throws_attempted, 0), 3) AS clutch_free_throw_pct,
        ROUND(
            ps.clutch_points
            / NULLIF(2 * (ps.clutch_field_goals_attempted + 0.44 * ps.clutch_free_throws_attempted), 0),
            3
        ) AS clutch_true_shooting_pct,
        ROUND(
            ps.points / NULLIF(2 * (ps.field_goals_attempted + 0.44 * ps.free_throws_attempted), 0), 3
        ) AS true_shooting_pct,
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
