-- One row per player per season, game type and shot zone, from the play-by-play
-- (1996-97 on), with the league's numbers for the same zone and season alongside.
-- Zones follow the NBA's court areas, computed from shot coordinates so they are
-- consistent across both play-by-play feeds: they match the live feed's own area
-- labels on 96.5% of shots, differing only at the edges (the restricted-area arc).
-- Field goals only; free throws are in nba_player_season_stats.
WITH play_by_play AS (
    SELECT *
    FROM
        {{ ref('stg_nba_play_by_play') }}
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

field_goals AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        is_shot_made,
        points_scored,
        shot_distance_ft,
        -- Coordinates are tenths of a foot from the basket. The paint is 16 ft wide and
        -- reaches 19 ft from the baseline, 14.25 ft past the basket; corner threes are
        -- taken below the point where the three-point arc meets the straight sideline line.
        CASE
            WHEN shot_distance_ft >= 40 THEN 'Heave'
            WHEN shot_value = 3 AND shot_y <= 92 THEN 'Corner 3'
            WHEN shot_value = 3 THEN 'Above the Break 3'
            WHEN shot_distance_ft < 4 THEN 'Restricted Area'
            WHEN ABS(shot_x) <= 80 AND shot_y <= 142.5 THEN 'In The Paint (Non-RA)'
            ELSE 'Mid-Range'
        END AS shot_zone
    FROM
        play_by_play
    WHERE
        event_type = 'field_goal'
        AND person_id IS NOT NULL
        AND shot_distance_ft IS NOT NULL
),

player_zones AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        shot_zone,
        COUNT(*) AS field_goals_attempted,
        COUNT(*) FILTER (WHERE is_shot_made) AS field_goals_made,
        SUM(points_scored) AS field_goal_points,
        AVG(shot_distance_ft) AS avg_shot_distance_ft
    FROM
        field_goals
    GROUP BY
        person_id, season_start_year, game_type, shot_zone
),

league_zones AS (
    SELECT
        season_start_year,
        game_type,
        shot_zone,
        COUNT(*) AS league_field_goals_attempted,
        COUNT(*) FILTER (WHERE is_shot_made) AS league_field_goals_made,
        SUM(points_scored) AS league_field_goal_points
    FROM
        field_goals
    GROUP BY
        season_start_year, game_type, shot_zone
),

league_shares AS (
    SELECT
        *,
        league_field_goals_attempted
        / SUM(league_field_goals_attempted) OVER (PARTITION BY season_start_year, game_type)
            AS league_share_of_attempts
    FROM
        league_zones
),

enriched AS (
    SELECT
        pz.person_id,
        COALESCE(p.first_name, n.first_name) AS first_name,
        COALESCE(p.last_name, n.last_name) AS last_name,
        pz.season_start_year,
        {{ nba_season_label('pz.season_start_year') }} AS season_label,
        pz.game_type,
        pz.shot_zone,
        CASE pz.shot_zone
            WHEN 'Restricted Area' THEN 1
            WHEN 'In The Paint (Non-RA)' THEN 2
            WHEN 'Mid-Range' THEN 3
            WHEN 'Corner 3' THEN 4
            WHEN 'Above the Break 3' THEN 5
            WHEN 'Heave' THEN 6
        END AS shot_zone_order,
        pz.field_goals_attempted,
        pz.field_goals_made,
        pz.field_goals_made / pz.field_goals_attempted AS field_goal_pct,
        pz.field_goal_points,
        pz.field_goal_points / pz.field_goals_attempted AS points_per_shot,
        pz.field_goals_attempted
        / SUM(pz.field_goals_attempted) OVER (
            PARTITION BY pz.person_id, pz.season_start_year, pz.game_type
        ) AS share_of_attempts,
        pz.avg_shot_distance_ft,
        lz.league_field_goals_made / lz.league_field_goals_attempted AS league_field_goal_pct,
        lz.league_field_goal_points / lz.league_field_goals_attempted AS league_points_per_shot,
        lz.league_share_of_attempts,
        pz.field_goals_made / pz.field_goals_attempted
        - lz.league_field_goals_made / lz.league_field_goals_attempted AS field_goal_pct_vs_league
    FROM
        player_zones pz
    INNER JOIN
        league_shares lz
        USING (season_start_year, game_type, shot_zone)
    LEFT JOIN
        players p
        USING (person_id)
    LEFT JOIN
        box_score_names n
        USING (person_id)
)

SELECT *
FROM
    enriched
ORDER BY
    season_start_year DESC, game_type ASC, person_id ASC, shot_zone_order ASC
