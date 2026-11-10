{% set possessions_start = nba_coverage_start('possessions') %}
{% set shooting = [
    'points', 'field_goals_made', 'field_goals_attempted', 'three_pointers_made', 'three_pointers_attempted',
    'free_throws_made', 'free_throws_attempted', 'assists', 'rebounds_total', 'opp_rebounds_total',
    'opp_field_goals_made', 'opp_field_goals_attempted', 'opp_three_pointers_made', 'opp_free_throws_made'
] %}
{% set full = [
    'points', 'opp_points', 'team_minutes', 'field_goals_made', 'field_goals_attempted', 'free_throws_attempted',
    'rebounds_offensive', 'rebounds_defensive', 'turnovers', 'opp_field_goals_made', 'opp_field_goals_attempted',
    'opp_free_throws_attempted', 'opp_rebounds_offensive', 'opp_rebounds_defensive', 'opp_turnovers'
] %}
-- One row per team per season per game type (Regular Season, Play-in
-- Tournament, Playoffs, NBA Cup Final) explaining how the team got its record:
-- ratings, pace, the Four Factors on both ends, shot profile, Pythagorean and
-- luck wins, SRS, and gaps to the league average. Covers every season from
-- 1946-47; each metric is null where its inputs were not recorded.
-- Every rate is computed from the season's summed counts with the formulas in
-- macros/nba_metrics.sql, never by averaging per-game rates. Possession metrics
-- (ratings, pace, turnover and rebound shares) use the games with a full box on
-- both sides, from 1973-74 on; shooting metrics use the games with box counts.
-- coverage_flag says whether those samples were all of the team's games.
-- SRS and SOS are regular season only.
WITH team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

srs AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_season_srs') }}
),

league AS (
    SELECT *
    FROM
        {{ ref('nba_league_season_baselines') }}
),

-- Transform
season_totals AS (
    SELECT
        team_id,
        season_start_year,
        game_type,
        COUNT(*) AS games_played,
        COUNT(*) FILTER (WHERE is_win) AS wins,
        COUNT(*) FILTER (WHERE NOT is_win) AS losses,
        COUNT(*) FILTER (WHERE counts_source <> 'none') AS games_with_counts,
        COUNT(*) FILTER (WHERE has_full_box AND season_start_year >= {{ possessions_start }}) AS games_with_full_box,
        SUM(points) AS total_points,
        SUM(opp_points) AS total_opp_points,
        -- Shooting sample: games with box counts.
        {% for c in shooting %}
        SUM({{ c }}) FILTER (WHERE counts_source <> 'none') AS s_{{ c }},
        {% endfor %}
        -- Possession sample: games with a full box on both sides, 1973-74 on.
        {% for c in full %}
        SUM({{ c }}) FILTER (WHERE has_full_box AND season_start_year >= {{ possessions_start }}) AS f_{{ c }},
        {% endfor %}
        SUM(points_in_the_paint) AS paint_points,
        SUM(points) FILTER (WHERE points_in_the_paint IS NOT NULL) AS paint_games_points,
        SUM(points_fast_break) AS fast_break_points,
        SUM(points) FILTER (WHERE points_fast_break IS NOT NULL) AS fast_break_games_points
    FROM
        team_games
    GROUP BY
        team_id, season_start_year, game_type
),

rated AS (
    SELECT
        *,
        {{
            nba_possessions(
                'f_field_goals_attempted', 'f_free_throws_attempted', 'f_rebounds_offensive',
                'f_rebounds_defensive', 'f_field_goals_made', 'f_turnovers',
                'f_opp_field_goals_attempted', 'f_opp_free_throws_attempted', 'f_opp_rebounds_offensive',
                'f_opp_rebounds_defensive', 'f_opp_field_goals_made', 'f_opp_turnovers'
            )
        }} AS possessions
    FROM
        season_totals
),

metrics AS (
    SELECT
        r.*,
        {{ nba_rating('r.f_points', 'r.possessions') }} AS ortg,
        {{ nba_rating('r.f_opp_points', 'r.possessions') }} AS drtg,
        {{ nba_pace('r.possessions', 'r.possessions', 'r.f_team_minutes') }} AS team_pace,
        {{ nba_efg('r.s_field_goals_made', 'r.s_three_pointers_made', 'r.s_field_goals_attempted') }} AS efg,
        {{ nba_ts('r.s_points', 'r.s_field_goals_attempted', 'r.s_free_throws_attempted') }} AS ts,
        {{ nba_pyth_wins('r.games_played', 'r.total_points', 'r.total_opp_points') }} AS pyth_wins
    FROM
        rated r
)

SELECT
    m.team_id,
    m.season_start_year,
    {{ nba_season_label('m.season_start_year') }} AS season_label,
    m.game_type,
    m.games_played,
    m.wins,
    m.losses,
    ROUND(m.possessions, 1) AS possessions,
    ROUND(m.ortg, 1) AS offensive_rating,
    ROUND(m.drtg, 1) AS defensive_rating,
    ROUND(m.ortg - m.drtg, 1) AS net_rating,
    ROUND(m.team_pace, 1) AS pace,
    ROUND(m.efg, 3) AS effective_field_goal_pct,
    ROUND(m.ts, 3) AS true_shooting_pct,
    ROUND({{ nba_ast_rate('m.s_assists', 'm.s_field_goals_made') }}, 3) AS assist_pct,
    ROUND({{ nba_reb_pct('m.s_rebounds_total', 'm.s_opp_rebounds_total') }}, 3) AS rebound_pct,
    ROUND({{ nba_tov_pct('m.f_turnovers', 'm.f_field_goals_attempted', 'm.f_free_throws_attempted') }}, 3)
        AS turnover_pct,
    CASE
        WHEN m.season_start_year >= {{ nba_coverage_start('three_pointers') }}
            THEN ROUND({{ nba_three_par('m.s_three_pointers_attempted', 'm.s_field_goals_attempted') }}, 3)
    END AS three_point_attempt_rate,
    ROUND(m.paint_points::DOUBLE / NULLIF(m.paint_games_points, 0), 3) AS points_in_paint_share,
    ROUND(m.fast_break_points::DOUBLE / NULLIF(m.fast_break_games_points, 0), 3) AS fast_break_points_share,
    ROUND({{ nba_reb_pct('m.f_rebounds_offensive', 'm.f_opp_rebounds_defensive') }}, 3) AS offensive_rebound_pct,
    ROUND({{ nba_ft_rate('m.s_free_throws_made', 'm.s_field_goals_attempted') }}, 3) AS free_throw_rate,
    ROUND(
        {{ nba_efg('m.s_opp_field_goals_made', 'm.s_opp_three_pointers_made', 'm.s_opp_field_goals_attempted') }}, 3
    ) AS opp_effective_field_goal_pct,
    ROUND(
        {{ nba_tov_pct('m.f_opp_turnovers', 'm.f_opp_field_goals_attempted', 'm.f_opp_free_throws_attempted') }}, 3
    ) AS opp_turnover_pct,
    ROUND({{ nba_reb_pct('m.f_rebounds_defensive', 'm.f_opp_rebounds_offensive') }}, 3) AS defensive_rebound_pct,
    ROUND({{ nba_ft_rate('m.s_opp_free_throws_made', 'm.s_opp_field_goals_attempted') }}, 3) AS opp_free_throw_rate,
    ROUND((m.total_points - m.total_opp_points)::DOUBLE / NULLIF(m.games_played, 0), 2) AS margin_of_victory,
    ROUND(m.pyth_wins, 1) AS pythagorean_wins,
    ROUND(m.wins - m.pyth_wins, 1) AS luck_wins,
    ROUND(s.srs, 2) AS simple_rating_system,
    ROUND(s.sos, 2) AS strength_of_schedule,
    ROUND(m.ortg - l.lg_offensive_rating, 1) AS relative_offensive_rating,
    ROUND(m.drtg - l.lg_offensive_rating, 1) AS relative_defensive_rating,
    ROUND(m.team_pace - l.lg_pace, 1) AS relative_pace,
    ROUND(m.efg - l.lg_effective_field_goal_pct, 3) AS relative_effective_field_goal_pct,
    ROUND(m.ts - l.lg_true_shooting_pct, 3) AS relative_true_shooting_pct,
    m.games_with_counts,
    m.games_with_full_box,
    CASE
        WHEN m.games_with_full_box = m.games_played THEN 'full'
        WHEN m.games_with_counts = m.games_played AND m.games_with_full_box = 0 THEN 'shooting_only'
        WHEN m.games_with_counts > 0 THEN 'partial'
        ELSE 'scores_only'
    END AS coverage_flag,
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    metrics m
LEFT JOIN
    srs s
    ON
        m.team_id = s.team_id
        AND m.season_start_year = s.season_start_year
        AND m.game_type = 'Regular Season'
LEFT JOIN
    league l
    ON
        m.season_start_year = l.season_start_year
        AND m.game_type = l.game_type
ORDER BY
    m.season_start_year DESC, m.game_type ASC, net_rating DESC
