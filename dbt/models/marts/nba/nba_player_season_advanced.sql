{% set sums = [
    'games_played', 'minutes_played', 'points', 'ts_points', 'ts_field_goals_attempted', 'ts_free_throws_attempted',
    'field_goals_made', 'field_goals_attempted', 'efg_three_pointers_made', 'three_pointers_attempted',
    'ft_rate_free_throws_made', 'ft_rate_field_goals_attempted', 'tov_pct_turnovers', 'tov_pct_plays',
    'usage_opportunity_numerator', 'usage_opportunity', 'assist_opportunity_numerator', 'assist_opportunity',
    'offensive_rebound_opportunity_numerator', 'offensive_rebound_opportunity',
    'defensive_rebound_opportunity_numerator', 'defensive_rebound_opportunity',
    'rebound_opportunity_numerator', 'rebound_opportunity', 'steal_opportunity_numerator', 'steal_opportunity',
    'block_opportunity_numerator', 'block_opportunity', 'player_possessions',
    'per_100_points', 'per_100_points_possessions', 'per_100_rebounds_total', 'per_100_rebounds_total_possessions',
    'per_100_assists', 'per_100_assists_possessions', 'per_100_steals', 'per_100_steals_possessions',
    'per_100_blocks', 'per_100_blocks_possessions', 'per_100_turnovers', 'per_100_turnovers_possessions',
    'game_score', 'game_score_games', 'rating_games', 'points_produced', 'individual_possessions'
] %}
-- One row per player per season per game type: the advanced metrics of
-- nba_player_stint_advanced with a traded player's stints combined. Every rate
-- re-divides the summed numerators and opportunities of the stints (each stint's
-- team context stays its own team's); individual offensive rating is total
-- points produced over total individual possessions, and individual defensive
-- rating is the stints' ratings weighted by the possessions they cover.
-- team_count and is_multi_team flag traded players. primary_team_id,
-- team_games_played, is_qualified and is_fg_qualified come from
-- nba_player_season_stats, so the two marts share one primary-team rule and one
-- set of qualification rules.
WITH stints AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_stints') }}
),

league AS (
    SELECT
        season_start_year,
        game_type,
        lg_true_shooting_pct
    FROM
        {{ ref('nba_league_season_baselines') }}
),

players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

season_stats AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        primary_team_id,
        team_games_played,
        is_qualified,
        is_fg_qualified
    FROM
        {{ ref('nba_player_season_stats') }}
),

-- Transform
seasons AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        {% for c in sums %}
        SUM({{ c }}) AS {{ c }},
        {% endfor %}
        SUM(individual_defensive_rating * rating_player_possessions)
        / NULLIF(SUM(rating_player_possessions) FILTER (WHERE individual_defensive_rating IS NOT NULL), 0)
            AS individual_defensive_rating,
        COUNT(*) AS team_count
    FROM
        stints
    GROUP BY
        person_id, season_start_year, game_type
),

enriched AS (
    SELECT
        s.*,
        l.lg_true_shooting_pct
    FROM
        seasons s
    LEFT JOIN
        league l
        USING (season_start_year, game_type)
)

SELECT
    e.person_id,
    p.first_name,
    p.last_name,
    e.season_start_year,
    {{ nba_season_label('e.season_start_year') }} AS season_label,
    e.game_type,
    ss.primary_team_id,
    e.team_count,
    e.team_count > 1 AS is_multi_team,
    e.games_played,
    ss.team_games_played,
    ss.is_qualified,
    ss.is_fg_qualified,
    e.minutes_played AS total_minutes,
    e.points AS total_points,
    {{ nba_player_metric_columns() }},
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    enriched e
LEFT JOIN
    players p
    USING (person_id)
LEFT JOIN
    season_stats ss
    USING (person_id, season_start_year, game_type)
