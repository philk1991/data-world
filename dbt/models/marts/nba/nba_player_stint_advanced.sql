-- One row per player per team per season per game type (a stint; a player
-- traded mid-season has one row per team): box-score advanced metrics built
-- from the player's games for that team. True shooting, effective field goal,
-- three-point and free throw rates; usage, assist, turnover, rebound, steal and
-- block percentages (team context from the same games); per-100-possession
-- production; Game Score per game; and Dean Oliver's individual offensive and
-- defensive ratings. Formulas: macros/nba_metrics.sql and
-- macros/nba_player_metric_columns.sql. nba_player_season_advanced combines a
-- traded player's stints. Each metric is null before its coverage start and
-- where its inputs were not recorded; rates are 0-1.
WITH stints AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_stints') }}
),

team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

-- Transform
league AS (
    SELECT
        season_start_year,
        game_type,
        {{
            nba_ts(
                "SUM(points) FILTER (WHERE counts_source <> 'none')",
                "SUM(field_goals_attempted) FILTER (WHERE counts_source <> 'none')",
                "SUM(free_throws_attempted) FILTER (WHERE counts_source <> 'none')"
            )
        }} AS lg_true_shooting_pct
    FROM
        team_games
    GROUP BY
        season_start_year, game_type
),

enriched AS (
    SELECT
        s.*,
        l.lg_true_shooting_pct
    FROM
        stints s
    LEFT JOIN
        league l
        USING (season_start_year, game_type)
)

SELECT
    e.person_id,
    p.first_name,
    p.last_name,
    e.team_id,
    e.season_start_year,
    {{ nba_season_label('e.season_start_year') }} AS season_label,
    e.game_type,
    e.games_played,
    e.minutes_played AS total_minutes,
    e.points AS total_points,
    {{ nba_player_metric_columns() }},
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    enriched e
LEFT JOIN
    players p
    USING (person_id)
