-- One row per player per season, game type and shot zone, from the play-by-play
-- (1996-97 on), with the league's numbers for the same zone and season alongside.
-- A rollup of nba_shot_events, which defines the zones; field goals with a
-- recorded distance only (free throws are in nba_player_season_stats).
WITH shots AS (
    SELECT *
    FROM
        {{ ref('nba_shot_events') }}
    WHERE
        shot_type = 'field_goal'
        AND shot_zone IS NOT NULL
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

player_zones AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        shot_zone,
        COUNT(*) AS field_goals_attempted,
        COUNT(*) FILTER (WHERE is_shot_made) AS field_goals_made,
        SUM(points_scored) AS field_goal_points,
        AVG(shot_distance_ft) AS avg_shot_distance_ft,
        MIN(shot_zone_order) AS shot_zone_order
    FROM
        shots
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
        shots
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
        pz.shot_zone_order,
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
