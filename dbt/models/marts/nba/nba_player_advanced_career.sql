-- One row per player per career scope (game_type Regular Season, the default
-- career, or Playoffs; plans/adr/0001-career-scope.md) summarising career
-- efficiency, enriched with bio. Seasons before nba_first_complete_season are
-- left out, as in nba_player_career_stats.
-- Box-score rates (usage, true shooting, effective field goal, assist and
-- rebound percentage, individual offensive/defensive rating) are recomputed
-- from the career's summed numerators and opportunities
-- (int_nba_player_stints, macros/nba_metrics.sql), so they cover every era
-- from each metric's coverage start, with nothing averaged across games.
-- The NBA-supplied on-court ratings (offensive_rating, defensive_rating,
-- net_rating) and PIE exist only in the advanced box scores (1996-97 on): the
-- ratings are weighted by each game's on-court possessions and PIE by minutes;
-- games_with_advanced counts those games. Double- and triple-doubles are
-- counted from the box score (int_nba_player_games) in every era, the same
-- definition as nba_player_game_stats.
WITH stints AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_stints') }}
    WHERE
        game_type IN {{ nba_career_game_types() }}
        AND season_start_year >= {{ nba_first_complete_season() }}
),

player_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_games') }}
    WHERE
        game_type IN {{ nba_career_game_types() }}
        AND season_start_year >= {{ nba_first_complete_season() }}
),

player_advanced AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics_extended') }}
    WHERE
        game_type IN {{ nba_career_game_types() }}
        AND season_start_year >= {{ nba_first_complete_season() }}
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
        game_type,
        SUM(games_played) AS games_played,
        SUM(minutes_played) AS total_minutes,
        SUM(usage_opportunity_numerator) AS usage_plays,
        SUM(usage_opportunity) AS usage_opportunity,
        SUM(ts_points) AS ts_points,
        SUM(ts_field_goals_attempted) AS ts_field_goals_attempted,
        SUM(ts_free_throws_attempted) AS ts_free_throws_attempted,
        SUM(field_goals_made) AS field_goals_made,
        SUM(field_goals_attempted) AS field_goals_attempted,
        SUM(efg_three_pointers_made) AS efg_three_pointers_made,
        SUM(assist_opportunity_numerator) AS assists,
        SUM(assist_opportunity) AS assist_opportunity,
        SUM(rebound_opportunity_numerator) AS rebounds,
        SUM(rebound_opportunity) AS rebound_opportunity,
        SUM(points_produced) AS points_produced,
        SUM(individual_possessions) AS individual_possessions,
        SUM(individual_defensive_rating * rating_player_possessions)
        / NULLIF(SUM(rating_player_possessions) FILTER (WHERE individual_defensive_rating IS NOT NULL), 0)
            AS individual_defensive_rating
    FROM
        stints
    GROUP BY
        person_id, game_type
),

-- Minutes per game counts only games with recorded minutes (early box scores
-- often leave them blank), the same denominator as nba_player_season_stats.
box_games AS (
    SELECT
        person_id,
        game_type,
        COUNT(minutes_played) AS games_with_minutes,
        COUNT(*) FILTER (WHERE is_double_double) AS double_doubles,
        COUNT(*) FILTER (WHERE is_triple_double) AS triple_doubles
    FROM
        player_games
    GROUP BY
        person_id, game_type
),

advanced_career AS (
    SELECT
        person_id,
        game_type,
        COUNT(DISTINCT game_id) AS games_with_advanced,
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
    GROUP BY
        person_id, game_type
)

SELECT
    b.person_id,
    p.first_name,
    p.last_name,
    b.game_type,
    p.is_guard,
    p.is_forward,
    p.is_center,
    b.games_played,
    COALESCE(a.games_with_advanced, 0) AS games_with_advanced,
    b.total_minutes / NULLIF(d.games_with_minutes, 0) AS minutes_per_game,
    COALESCE(d.double_doubles, 0) AS double_doubles,
    COALESCE(d.triple_doubles, 0) AS triple_doubles,
    b.usage_plays / NULLIF(b.usage_opportunity, 0) AS usage_pct,
    {{ nba_ts('b.ts_points', 'b.ts_field_goals_attempted', 'b.ts_free_throws_attempted') }}
        AS true_shooting_pct,
    {{ nba_efg('b.field_goals_made', 'b.efg_three_pointers_made', 'b.field_goals_attempted') }}
        AS effective_field_goal_pct,
    a.on_court_offensive_rating AS offensive_rating,
    a.on_court_defensive_rating AS defensive_rating,
    a.on_court_offensive_rating - a.on_court_defensive_rating AS net_rating,
    b.assists / NULLIF(b.assist_opportunity, 0) AS assist_pct,
    b.rebounds / NULLIF(b.rebound_opportunity, 0) AS rebound_pct,
    a.w_pie AS player_impact_estimate,
    100 * b.points_produced / NULLIF(b.individual_possessions, 0) AS individual_offensive_rating,
    b.individual_defensive_rating,
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    box_career b
LEFT JOIN
    box_games d
    USING (person_id, game_type)
LEFT JOIN
    advanced_career a
    USING (person_id, game_type)
LEFT JOIN
    players p
    USING (person_id)
ORDER BY
    b.game_type DESC, triple_doubles DESC, net_rating DESC
