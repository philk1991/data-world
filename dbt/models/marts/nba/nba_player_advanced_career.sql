-- One row per player summarising career efficiency over competitive games
-- (Regular Season, Playoffs, Play-in Tournament and NBA Cup Final), enriched
-- with bio. Box-score rates (usage, true shooting, effective field goal,
-- assist and rebound percentage, individual offensive/defensive rating) are
-- recomputed from the career's summed numerators and opportunities
-- (int_nba_player_stints, macros/nba_metrics.sql), so they cover every era from
-- each metric's coverage start, with nothing averaged across games.
-- The NBA-supplied on-court ratings (offensive_rating, defensive_rating,
-- net_rating) and PIE exist only in the advanced box scores (1996-97 on): the
-- ratings are weighted by each game's on-court possessions (summing points per
-- possession, not averaging rates) and PIE by minutes. games_with_advanced and
-- the double/triple-double counts cover those games.
WITH stints AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_stints') }}
),

player_advanced AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics_extended') }}
),

players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

-- Transform
box_career AS (
    SELECT
        person_id,
        SUM(games_played) AS games_played,
        SUM(minutes_played) AS total_minutes,
        SUM(usage_opportunity_numerator) FILTER (WHERE season_start_year >= 1977) AS usage_plays,
        SUM(usage_opportunity) FILTER (WHERE season_start_year >= 1977) AS usage_opportunity,
        SUM(ts_points) AS ts_points,
        SUM(ts_field_goals_attempted) AS ts_field_goals_attempted,
        SUM(ts_free_throws_attempted) AS ts_free_throws_attempted,
        SUM(field_goals_made) AS field_goals_made,
        SUM(field_goals_attempted) AS field_goals_attempted,
        SUM(three_pointers_made) AS three_pointers_made,
        SUM(assist_opportunity_numerator) FILTER (WHERE season_start_year >= 1964) AS assists,
        SUM(assist_opportunity) FILTER (WHERE season_start_year >= 1964) AS assist_opportunity,
        SUM(rebound_opportunity_numerator) FILTER (WHERE season_start_year >= 1964) AS rebounds,
        SUM(rebound_opportunity) FILTER (WHERE season_start_year >= 1964) AS rebound_opportunity,
        SUM(points_produced) AS points_produced,
        SUM(individual_possessions) AS individual_possessions,
        SUM(individual_defensive_rating * rating_player_possessions)
        / NULLIF(SUM(rating_player_possessions) FILTER (WHERE individual_defensive_rating IS NOT NULL), 0)
            AS individual_defensive_rating
    FROM
        stints
    GROUP BY
        person_id
),

-- Minutes per game counts only stints with recorded minutes (none before
-- 1964-65).
minute_games AS (
    SELECT
        person_id,
        SUM(games_played) AS games_with_minutes
    FROM
        stints
    WHERE
        minutes_played IS NOT NULL
    GROUP BY
        person_id
),

advanced_career AS (
    SELECT
        person_id,
        COUNT(DISTINCT game_id) AS games_with_advanced,
        COUNT(CASE WHEN is_double_double THEN 1 END) AS double_doubles,
        COUNT(CASE WHEN is_triple_double THEN 1 END) AS triple_doubles,
        SUM(offensive_rating * possessions)
        / NULLIF(SUM(possessions) FILTER (WHERE offensive_rating IS NOT NULL), 0) AS on_court_offensive_rating,
        SUM(defensive_rating * possessions)
        / NULLIF(SUM(possessions) FILTER (WHERE defensive_rating IS NOT NULL), 0) AS on_court_defensive_rating,
        SUM(player_impact_estimate * minutes_played)
        / NULLIF(SUM(minutes_played) FILTER (WHERE player_impact_estimate IS NOT NULL), 0) AS w_pie
    FROM
        player_advanced
    WHERE
        person_id IS NOT NULL
        AND minutes_played > 0
        AND game_type IN ('Regular Season', 'Playoffs', 'Play-in Tournament', 'NBA Cup Final')
    GROUP BY
        person_id
)

SELECT
    b.person_id,
    p.first_name,
    p.last_name,
    p.is_guard,
    p.is_forward,
    p.is_center,
    b.games_played,
    COALESCE(a.games_with_advanced, 0) AS games_with_advanced,
    ROUND(b.total_minutes / NULLIF(m.games_with_minutes, 0), 1) AS minutes_per_game,
    COALESCE(a.double_doubles, 0) AS double_doubles,
    COALESCE(a.triple_doubles, 0) AS triple_doubles,
    ROUND(b.usage_plays / NULLIF(b.usage_opportunity, 0), 3) AS usage_pct,
    ROUND({{ nba_ts('b.ts_points', 'b.ts_field_goals_attempted', 'b.ts_free_throws_attempted') }}, 3)
        AS true_shooting_pct,
    ROUND({{ nba_efg('b.field_goals_made', 'b.three_pointers_made', 'b.field_goals_attempted') }}, 3)
        AS effective_field_goal_pct,
    ROUND(a.on_court_offensive_rating, 1) AS offensive_rating,
    ROUND(a.on_court_defensive_rating, 1) AS defensive_rating,
    ROUND(a.on_court_offensive_rating - a.on_court_defensive_rating, 1) AS net_rating,
    ROUND(b.assists / NULLIF(b.assist_opportunity, 0), 3) AS assist_pct,
    ROUND(b.rebounds / NULLIF(b.rebound_opportunity, 0), 3) AS rebound_pct,
    ROUND(a.w_pie, 3) AS player_impact_estimate,
    ROUND(100 * b.points_produced / NULLIF(b.individual_possessions, 0), 1) AS individual_offensive_rating,
    ROUND(b.individual_defensive_rating, 1) AS individual_defensive_rating,
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    box_career b
LEFT JOIN
    minute_games m
    USING (person_id)
LEFT JOIN
    advanced_career a
    USING (person_id)
LEFT JOIN
    players p
    USING (person_id)
ORDER BY
    triple_doubles DESC, net_rating DESC
