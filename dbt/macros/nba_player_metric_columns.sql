{#
    The select-list of player metrics, rendered from the sums in
    int_nba_player_stints (or the same sums added across a player's stints).
    nba_player_stint_advanced and nba_player_season_advanced both call it, so a
    player rate has one definition at every grain. Needs season_start_year and
    lg_true_shooting_pct (the league TS% for the season and game type) in scope.

    Each metric is null before its coverage start (brief section 3):
    AST% 1964-65; ORB%, DRB%, STL%, BLK%, per-100 and defensive rating 1973-74;
    usage, TOV% and offensive rating 1977-78; three-point rate 1979-80.
    Rates are 0-1.
#}
{% macro nba_player_metric_columns() %}
    {%- set rates = [
        ('assist_pct', 'assist_opportunity', nba_coverage_start('assists')),
        ('offensive_rebound_pct', 'offensive_rebound_opportunity', nba_coverage_start('rebound_split')),
        ('defensive_rebound_pct', 'defensive_rebound_opportunity', nba_coverage_start('rebound_split')),
        ('rebound_pct', 'rebound_opportunity', nba_coverage_start('total_rebounds')),
        ('steal_pct', 'steal_opportunity', nba_coverage_start('steals_blocks')),
        ('block_pct', 'block_opportunity', nba_coverage_start('steals_blocks'))
    ] -%}
    {{ nba_ts('ts_points', 'ts_field_goals_attempted', 'ts_free_throws_attempted') }} AS true_shooting_pct,
    {{ nba_efg('field_goals_made', 'three_pointers_made', 'field_goals_attempted') }}
        AS effective_field_goal_pct,
    CASE
        WHEN season_start_year >= {{ nba_coverage_start('three_pointers') }}
            THEN {{ nba_three_par('three_pointers_attempted', 'field_goals_attempted') }}
    END AS three_point_attempt_rate,
    {{ nba_ft_rate('ft_rate_free_throws_made', 'ft_rate_field_goals_attempted') }} AS free_throw_rate,
    -- Points above what league-average true shooting would score on the same attempts.
    ts_points - 2 * lg_true_shooting_pct * (ts_field_goals_attempted + 0.44 * ts_free_throws_attempted)
        AS true_shooting_points_added,
    CASE
        WHEN season_start_year >= {{ nba_coverage_start('turnovers') }}
            THEN usage_opportunity_numerator / NULLIF(usage_opportunity, 0)
    END AS usage_pct,
    CASE
        WHEN season_start_year >= {{ nba_coverage_start('turnovers') }}
            THEN tov_pct_turnovers::DOUBLE / NULLIF(tov_pct_plays, 0)
    END AS turnover_pct,
    {% for name, opp, start in rates %}
    CASE
        WHEN season_start_year >= {{ start }}
            THEN {{ opp }}_numerator / NULLIF({{ opp }}, 0)
    END AS {{ name }},
    {% endfor %}
    player_possessions,
    {% for c in ['points', 'rebounds_total', 'assists', 'steals', 'blocks', 'turnovers'] %}
    100 * per_100_{{ c }} / NULLIF(per_100_{{ c }}_possessions, 0) AS {{ c }}_per_100,
    {% endfor %}
    game_score / NULLIF(game_score_games, 0) AS game_score_per_game,
    rating_games,
    points_produced,
    individual_possessions,
    100 * points_produced / NULLIF(individual_possessions, 0) AS individual_offensive_rating,
    individual_defensive_rating
{% endmacro %}
