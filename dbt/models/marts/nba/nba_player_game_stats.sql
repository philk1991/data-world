-- One row per player per game played: the traditional box score with game
-- context, plus advanced efficiency from the advanced box scores (1996-97 on;
-- null before). Built on int_nba_player_games, so the team is resolved where the
-- raw data leaves it blank (all of 2021-22) and nba_player_season_stats, built on
-- the same rows, adds up from it exactly. Shooting percentages are only set when
-- attempts were recorded. game_score is Hollinger's Game Score
-- (macros/nba_metrics.sql), null where any of its inputs was not recorded.
-- Double-doubles come from int_nba_player_games.
-- The component columns (ts_*, efg_three_pointers_made, the *_opportunity pairs,
-- tov_pct_*, player_possessions, per_100_*) are the additive inputs every player
-- rate divides, from the same macros as the season and stint models, so Cube can
-- sum them over any games (plans/adr/0002-dbt-cube-boundary.md). The team-context
-- ones come from int_nba_player_game_context and are null outside competitive
-- games and wherever an input wasn't recorded.
WITH player_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_games') }}
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

game_context AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_game_context') }}
),

-- Transform
shooting_components AS (
    SELECT
        game_id,
        person_id,
        {{ nba_shooting_components() }}
    FROM
        player_games
),

rate_components AS (
    SELECT
        game_id,
        person_id,
        {{ nba_player_rate_components() }}
    FROM
        game_context
)

SELECT
    b.person_id,
    b.game_id,
    COALESCE(p.first_name, b.first_name) AS first_name,
    COALESCE(p.last_name, b.last_name) AS last_name,
    b.game_date,
    b.season_start_year,
    {{ nba_season_label('b.season_start_year') }} AS season_label,
    b.game_type,
    b.is_competitive,
    b.team_id AS player_team_id,
    b.opponent_team_id,
    b.is_team_inferred,
    b.is_home,
    b.is_win,
    b.is_starter,
    b.starting_position,
    b.minutes_played,
    b.points,
    b.rebounds_offensive,
    b.rebounds_defensive,
    b.rebounds_total,
    b.assists,
    b.steals,
    b.blocks,
    b.turnovers,
    b.fouls_personal,
    b.field_goals_made,
    b.field_goals_attempted,
    ROUND(b.field_goals_made / NULLIF(b.field_goals_attempted, 0), 3) AS field_goal_pct,
    b.three_pointers_made,
    b.three_pointers_attempted,
    ROUND(b.three_pointers_made / NULLIF(b.three_pointers_attempted, 0), 3) AS three_point_pct,
    b.free_throws_made,
    b.free_throws_attempted,
    ROUND(b.free_throws_made / NULLIF(b.free_throws_attempted, 0), 3) AS free_throw_pct,
    b.plus_minus_points,
    ROUND(
        {{
            nba_game_score(
                'b.points', 'b.field_goals_made', 'b.field_goals_attempted', 'b.free_throws_made',
                'b.free_throws_attempted', 'b.rebounds_offensive', 'b.rebounds_defensive', 'b.steals',
                'b.assists', 'b.blocks', 'b.fouls_personal', 'b.turnovers'
            )
        }}, 1
    ) AS game_score,
    ROUND(a.usage_percentage, 3) AS usage_pct,
    ROUND(a.true_shooting_percentage, 3) AS true_shooting_pct,
    ROUND(a.effective_field_goal_percentage, 3) AS effective_field_goal_pct,
    ROUND(a.offensive_rating, 1) AS offensive_rating,
    ROUND(a.defensive_rating, 1) AS defensive_rating,
    ROUND(a.net_rating, 1) AS net_rating,
    ROUND(a.assist_percentage, 3) AS assist_pct,
    ROUND(a.rebound_percentage, 3) AS rebound_pct,
    ROUND(a.player_impact_estimate, 3) AS player_impact_estimate,
    b.is_double_double,
    b.is_triple_double,
    s.* EXCLUDE (game_id, person_id),
    r.* EXCLUDE (game_id, person_id),
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    player_games b
LEFT JOIN
    players p
    USING (person_id)
LEFT JOIN
    player_advanced a
    USING (game_id, person_id)
LEFT JOIN
    shooting_components s
    USING (game_id, person_id)
LEFT JOIN
    rate_components r
    USING (game_id, person_id)
ORDER BY
    b.game_date DESC, b.game_id ASC, b.points DESC
