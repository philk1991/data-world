-- One row per team per competitive game (Regular Season, Play-in Tournament,
-- Playoffs, NBA Cup Final): box counts for both sides, box-estimated possessions
-- and pace, offensive/defensive/net rating, the eight Four Factors and style rates.
-- Every formula comes from macros/nba_metrics.sql. Single-game rates are noisy:
-- to compare periods, sum the counts and recompute, never average these rows.
-- Possession-based metrics start in 1973-74 (offensive rebounds and turnovers
-- were not recorded before) and are null where any input is missing. Counts
-- before 1983-84 are summed from player box scores (counts_source = player_sum).
WITH team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

-- Transform
gated AS (
    SELECT
        *,
        CASE WHEN season_start_year >= 1973 THEN possessions END AS rated_possessions
    FROM
        team_games
)

SELECT
    game_id,
    team_id,
    opponent_team_id,
    season_start_year,
    season_start_year::VARCHAR || '-'
    || RIGHT((season_start_year + 1)::VARCHAR, 2) AS season_label,
    game_type,
    game_date,
    is_home,
    is_win,
    overtime_periods,
    team_minutes,
    points,
    opp_points,
    points - opp_points AS point_margin,
    field_goals_made,
    field_goals_attempted,
    three_pointers_made,
    three_pointers_attempted,
    free_throws_made,
    free_throws_attempted,
    rebounds_offensive,
    rebounds_defensive,
    rebounds_total,
    assists,
    steals,
    blocks,
    turnovers,
    fouls_personal,
    opp_field_goals_made,
    opp_field_goals_attempted,
    opp_three_pointers_made,
    opp_three_pointers_attempted,
    opp_free_throws_made,
    opp_free_throws_attempted,
    opp_rebounds_offensive,
    opp_rebounds_defensive,
    opp_rebounds_total,
    opp_assists,
    opp_steals,
    opp_blocks,
    opp_turnovers,
    opp_fouls_personal,
    ROUND(rated_possessions, 1) AS possessions,
    ROUND({{ nba_pace('rated_possessions', 'rated_possessions', 'team_minutes') }}, 1) AS pace,
    ROUND({{ nba_rating('points', 'rated_possessions') }}, 1) AS offensive_rating,
    ROUND({{ nba_rating('opp_points', 'rated_possessions') }}, 1) AS defensive_rating,
    ROUND(
        {{ nba_rating('points', 'rated_possessions') }} - {{ nba_rating('opp_points', 'rated_possessions') }}, 1
    ) AS net_rating,
    ROUND({{ nba_efg('field_goals_made', 'three_pointers_made', 'field_goals_attempted') }}, 3)
        AS effective_field_goal_pct,
    ROUND({{ nba_tov_pct('turnovers', 'field_goals_attempted', 'free_throws_attempted') }}, 3) AS turnover_pct,
    ROUND({{ nba_reb_pct('rebounds_offensive', 'opp_rebounds_defensive') }}, 3) AS offensive_rebound_pct,
    ROUND({{ nba_ft_rate('free_throws_made', 'field_goals_attempted') }}, 3) AS free_throw_rate,
    ROUND({{ nba_efg('opp_field_goals_made', 'opp_three_pointers_made', 'opp_field_goals_attempted') }}, 3)
        AS opp_effective_field_goal_pct,
    ROUND({{ nba_tov_pct('opp_turnovers', 'opp_field_goals_attempted', 'opp_free_throws_attempted') }}, 3)
        AS opp_turnover_pct,
    ROUND({{ nba_reb_pct('rebounds_defensive', 'opp_rebounds_offensive') }}, 3) AS defensive_rebound_pct,
    ROUND({{ nba_ft_rate('opp_free_throws_made', 'opp_field_goals_attempted') }}, 3) AS opp_free_throw_rate,
    ROUND({{ nba_reb_pct('rebounds_total', 'opp_rebounds_total') }}, 3) AS rebound_pct,
    -- The three-point line arrived in 1979-80; the rate is null, not 0, before it.
    CASE
        WHEN season_start_year >= 1979
            THEN ROUND({{ nba_three_par('three_pointers_attempted', 'field_goals_attempted') }}, 3)
    END AS three_point_attempt_rate,
    ROUND({{ nba_ast_rate('assists', 'field_goals_made') }}, 3) AS assist_pct,
    ROUND({{ nba_ts('points', 'field_goals_attempted', 'free_throws_attempted') }}, 3) AS true_shooting_pct,
    counts_source,
    has_full_box,
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    gated
