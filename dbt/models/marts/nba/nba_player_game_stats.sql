-- One row per player per game played: the traditional box score with game
-- context, plus advanced efficiency from the advanced box scores (1996-97 on;
-- null before). Uses the same played-game filter as nba_player_season_stats
-- (minutes_played not null), so summing a player's rows for a season and game
-- type gives that mart's games_played and totals. Shooting percentages are only
-- set when attempts were recorded. game_score is Hollinger's Game Score
-- (macros/nba_metrics.sql), null where any of its inputs was not recorded.
WITH box_scores AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics') }}
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
played AS (
    SELECT *
    FROM
        box_scores
    WHERE
        person_id IS NOT NULL
        AND minutes_played IS NOT NULL
        AND game_date IS NOT NULL
        AND game_type IS NOT NULL
),

enriched AS (
    SELECT
        b.person_id,
        b.game_id,
        COALESCE(p.first_name, b.first_name) AS first_name,
        COALESCE(p.last_name, b.last_name) AS last_name,
        b.game_date,
        b.season_start_year,
        b.season_start_year::VARCHAR || '-'
        || RIGHT((b.season_start_year + 1)::VARCHAR, 2) AS season_label,
        b.game_type,
        b.player_team_id,
        b.opponent_team_id,
        b.is_home,
        b.is_win,
        b.starting_position IS NOT NULL AS is_starter,
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
        -- Categories in double figures among points, rebounds, assists, steals and blocks.
        (b.points >= 10)::INTEGER
        + (b.rebounds_total >= 10)::INTEGER
        + (b.assists >= 10)::INTEGER
        + COALESCE((b.steals >= 10)::INTEGER, 0)
        + COALESCE((b.blocks >= 10)::INTEGER, 0) AS double_digit_categories,
        ROUND(a.usage_percentage, 3) AS usage_pct,
        ROUND(a.true_shooting_percentage, 3) AS true_shooting_pct,
        ROUND(a.effective_field_goal_percentage, 3) AS effective_field_goal_pct,
        ROUND(a.offensive_rating, 1) AS offensive_rating,
        ROUND(a.defensive_rating, 1) AS defensive_rating,
        ROUND(a.net_rating, 1) AS net_rating,
        ROUND(a.assist_percentage, 3) AS assist_pct,
        ROUND(a.rebound_percentage, 3) AS rebound_pct,
        ROUND(a.player_impact_estimate, 3) AS player_impact_estimate
    FROM
        played b
    LEFT JOIN
        players p
        USING (person_id)
    LEFT JOIN
        player_advanced a
        USING (game_id, person_id)
)

SELECT
    * EXCLUDE (double_digit_categories),
    COALESCE(double_digit_categories >= 2, FALSE) AS is_double_double,
    COALESCE(double_digit_categories >= 3, FALSE) AS is_triple_double
FROM
    enriched
ORDER BY
    game_date DESC, game_id ASC, points DESC
