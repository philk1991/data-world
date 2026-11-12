-- One row per play-by-play event credited to a player (1996-97 on), with the
-- game context every play-by-play mart needs: the score before the event, the
-- player's team margin and whether the event falls in clutch time. Clutch time
-- is the NBA's definition: the last five minutes of the fourth quarter or any
-- overtime, with the score within five points. It is judged on the score before
-- the event, so the shot that opens a six-point lead still counts. The one
-- clutch definition nba_shot_events and nba_player_clutch_stats read.
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

-- Transform
-- The score before an event is the previous event's score, so the window runs
-- over every event, before the filter to player events.
events AS (
    SELECT
        pbp.*,
        g.game_date,
        pbp.team_id = g.home_team_id AS is_home,
        CASE
            WHEN pbp.team_id = g.home_team_id THEN g.away_team_id
            WHEN pbp.team_id = g.away_team_id THEN g.home_team_id
        END AS opponent_team_id,
        COALESCE(LAG(pbp.score_home) OVER game_order, 0) AS score_home_before,
        COALESCE(LAG(pbp.score_away) OVER game_order, 0) AS score_away_before
    FROM
        play_by_play pbp
    LEFT JOIN
        games g
        USING (game_id)
    WINDOW game_order AS (PARTITION BY pbp.game_id ORDER BY pbp.event_order)
)

SELECT
    game_id,
    action_number,
    event_order,
    season_start_year,
    game_type,
    game_date,
    period,
    clock_seconds_remaining,
    event_type,
    person_id,
    team_id,
    opponent_team_id,
    is_home,
    is_shot_made,
    shot_value,
    points_scored,
    shot_x,
    shot_y,
    shot_distance_ft,
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
