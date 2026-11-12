-- One row per shot attempt by a player from the play-by-play (1996-97 on): every
-- field goal and free throw, with its zone, distance, result and clutch context.
-- The atomic fact behind nba_player_shot_zones and the clutch shooting in
-- nba_player_clutch_stats, so Cube can compute shooting by zone, clutch time,
-- period or any other cut from one grain (plans/adr/0002-dbt-cube-boundary.md).
-- Zones follow the NBA's court areas, computed from shot coordinates so they are
-- consistent across both play-by-play feeds: they match the live feed's own area
-- labels on 96.5% of shots, differing only at the edges (the restricted-area arc).
-- shot_zone is null for free throws and for the few field goals with no recorded
-- distance. Counts come from the play-by-play, so they can differ slightly from
-- the box score.
WITH play_events AS (
    SELECT *
    FROM
        {{ ref('int_nba_play_events') }}
    WHERE
        event_type IN ('field_goal', 'free_throw')
),

-- Transform
zoned AS (
    SELECT
        *,
        -- Coordinates are tenths of a foot from the basket. The paint is 16 ft wide and
        -- reaches 19 ft from the baseline, 14.25 ft past the basket; corner threes are
        -- taken below the point where the three-point arc meets the straight sideline line.
        CASE
            WHEN event_type <> 'field_goal' OR shot_distance_ft IS NULL THEN NULL
            WHEN shot_distance_ft >= 40 THEN 'Heave'
            WHEN shot_value = 3 AND shot_y <= 92 THEN 'Corner 3'
            WHEN shot_value = 3 THEN 'Above the Break 3'
            WHEN shot_distance_ft < 4 THEN 'Restricted Area'
            WHEN ABS(shot_x) <= 80 AND shot_y <= 142.5 THEN 'In The Paint (Non-RA)'
            ELSE 'Mid-Range'
        END AS shot_zone
    FROM
        play_events
)

SELECT
    game_id,
    action_number,
    person_id,
    team_id,
    opponent_team_id,
    season_start_year,
    {{ nba_season_label('season_start_year') }} AS season_label,
    game_type,
    game_date,
    period,
    clock_seconds_remaining,
    event_type AS shot_type,
    shot_value,
    COALESCE(is_shot_made, FALSE) AS is_shot_made,
    COALESCE(points_scored, 0) AS points_scored,
    shot_zone,
    CASE shot_zone
        WHEN 'Restricted Area' THEN 1
        WHEN 'In The Paint (Non-RA)' THEN 2
        WHEN 'Mid-Range' THEN 3
        WHEN 'Corner 3' THEN 4
        WHEN 'Above the Break 3' THEN 5
        WHEN 'Heave' THEN 6
    END AS shot_zone_order,
    shot_distance_ft,
    shot_x,
    shot_y,
    is_clutch,
    team_margin_before,
    -- A made field goal that took the team from tied or behind to ahead.
    COALESCE(
        event_type = 'field_goal' AND is_shot_made
        AND team_margin_before <= 0 AND team_margin_before + points_scored > 0,
        FALSE
    ) AS is_go_ahead
FROM
    zoned
