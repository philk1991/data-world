{% set possessions_start = nba_coverage_start('possessions') %}
{% set counts = [
    'points', 'field_goals_made', 'field_goals_attempted', 'three_pointers_made', 'three_pointers_attempted',
    'free_throws_made', 'free_throws_attempted', 'rebounds_offensive', 'rebounds_defensive', 'rebounds_total',
    'assists', 'steals', 'blocks', 'turnovers', 'fouls_personal', 'team_minutes'
] %}
{% set shooting = [
    'points', 'field_goals_made', 'field_goals_attempted', 'three_pointers_made', 'three_pointers_attempted',
    'free_throws_made', 'free_throws_attempted'
] %}
{% set full = [
    'points', 'field_goals_made', 'field_goals_attempted', 'free_throws_attempted', 'rebounds_offensive',
    'rebounds_defensive', 'turnovers', 'team_minutes', 'opp_field_goals_made', 'opp_field_goals_attempted',
    'opp_free_throws_attempted', 'opp_rebounds_offensive', 'opp_rebounds_defensive', 'opp_turnovers'
] %}
-- One row per season per game type: league totals and league-average rates,
-- the baseline every relative and era-adjusted NBA metric compares against.
-- Rates are built from the summed numerators and denominators of every team
-- game, never from averaged team rates.
-- A league total is only set when every team game of the season and game type
-- recorded that count; otherwise it is null. Rates use the team games that
-- recorded their inputs (shooting rates: games with box counts; possession,
-- turnover and rebound rates: games with a full box on both sides), and the
-- sample sizes say how many that was. Possessions are estimated from the
-- season's summed counts, not by adding up per-game estimates.
WITH team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

-- Transform
league AS (
    SELECT
        season_start_year,
        game_type,
        {% for c in counts %}
        CASE WHEN COUNT({{ c }}) = COUNT(*) THEN SUM({{ c }}) END AS lg_{{ c }},
        {% endfor %}
        -- Shooting sample: team games with box counts.
        {% for c in shooting %}
        SUM({{ c }}) FILTER (WHERE counts_source <> 'none') AS s_{{ c }},
        {% endfor %}
        -- Possession sample: team games with a full box on both sides, 1973-74 on.
        {% for c in full %}
        SUM({{ c }}) FILTER (WHERE has_full_box AND season_start_year >= {{ possessions_start }}) AS f_{{ c }},
        {% endfor %}
        COUNT(*) AS team_games,
        COUNT(*) FILTER (WHERE counts_source <> 'none') AS team_games_with_counts,
        COUNT(*) FILTER (WHERE has_full_box AND season_start_year >= {{ possessions_start }})
            AS team_games_with_full_box,
        SUM(points) AS all_points
    FROM
        team_games
    GROUP BY
        season_start_year, game_type
),

possessions AS (
    SELECT
        *,
        {{
            nba_possessions(
                'f_field_goals_attempted', 'f_free_throws_attempted', 'f_rebounds_offensive',
                'f_rebounds_defensive', 'f_field_goals_made', 'f_turnovers',
                'f_opp_field_goals_attempted', 'f_opp_free_throws_attempted', 'f_opp_rebounds_offensive',
                'f_opp_rebounds_defensive', 'f_opp_field_goals_made', 'f_opp_turnovers'
            )
        }} AS f_possessions
    FROM
        league
)

SELECT
    season_start_year,
    {{ nba_season_label('season_start_year') }} AS season_label,
    game_type,
    team_games,
    team_games_with_counts,
    team_games_with_full_box,
    lg_points,
    lg_field_goals_made,
    lg_field_goals_attempted,
    lg_three_pointers_made,
    lg_three_pointers_attempted,
    lg_free_throws_made,
    lg_free_throws_attempted,
    lg_rebounds_offensive,
    lg_rebounds_defensive,
    lg_rebounds_total,
    lg_assists,
    lg_steals,
    lg_blocks,
    lg_turnovers,
    lg_fouls_personal,
    lg_team_minutes,
    -- League possessions: a total only when every team game had a full box.
    CASE WHEN team_games_with_full_box = team_games THEN ROUND(f_possessions, 1) END AS lg_possessions,
    ROUND(all_points::DOUBLE / NULLIF(team_games, 0), 1) AS lg_points_per_game,
    ROUND({{ nba_pace('f_possessions', 'f_possessions', 'f_team_minutes') }}, 1) AS lg_pace,
    ROUND(f_points / NULLIF(f_possessions, 0), 4) AS lg_points_per_possession,
    ROUND({{ nba_rating('f_points', 'f_possessions') }}, 1) AS lg_offensive_rating,
    ROUND({{ nba_ts('s_points', 's_field_goals_attempted', 's_free_throws_attempted') }}, 3) AS lg_true_shooting_pct,
    ROUND({{ nba_efg('s_field_goals_made', 's_three_pointers_made', 's_field_goals_attempted') }}, 3)
        AS lg_effective_field_goal_pct,
    CASE
        WHEN season_start_year >= {{ nba_coverage_start('three_pointers') }}
            THEN ROUND({{ nba_three_par('s_three_pointers_attempted', 's_field_goals_attempted') }}, 3)
    END AS lg_three_point_attempt_rate,
    ROUND({{ nba_ft_rate('s_free_throws_made', 's_field_goals_attempted') }}, 3) AS lg_free_throw_rate,
    ROUND({{ nba_tov_pct('f_turnovers', 'f_field_goals_attempted', 'f_free_throws_attempted') }}, 3)
        AS lg_turnover_pct,
    ROUND({{ nba_reb_pct('f_rebounds_offensive', 'f_opp_rebounds_defensive') }}, 3) AS lg_offensive_rebound_pct,
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    possessions
