-- One row per player per career scope: game_type is Regular Season (the
-- default career, as on NBA.com) or Playoffs. The two rows add up: sum the
-- totals across both and recompute the rates from the summed made/attempted
-- columns for a combined career. Play-in and NBA Cup final games count toward
-- neither (plans/adr/0001-career-scope.md).
-- A convenience rollup of nba_player_season_stats, so it reconciles with the
-- season rows by construction. Seasons before nba_first_complete_season are
-- left out: their schedules are missing every game against a defunct franchise
-- (plans/adr/0003-coverage-cutoff.md). has_games_before_coverage flags careers
-- that started earlier, whose totals are therefore partial.
WITH season_stats AS (
    SELECT *
    FROM
        {{ ref('nba_player_season_stats') }}
    WHERE
        game_type IN {{ nba_career_game_types() }}
),

players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

-- Transform
career AS (
    SELECT
        person_id,
        game_type,
        ARG_MAX(first_name, season_start_year) AS first_name,
        ARG_MAX(last_name, season_start_year) AS last_name,
        COUNT(*) AS seasons_played,
        MIN(season_start_year) AS first_season_start_year,
        MAX(season_start_year) AS last_season_start_year,
        MIN(first_game_date) AS first_game_date,
        MAX(last_game_date) AS last_game_date,
        SUM(games_played) AS games_played,
        SUM(total_minutes) AS total_minutes,
        SUM(total_points) AS total_points,
        SUM(total_rebounds) AS total_rebounds,
        SUM(total_assists) AS total_assists,
        SUM(total_steals) AS total_steals,
        SUM(total_blocks) AS total_blocks,
        SUM(total_turnovers) AS total_turnovers,
        SUM(total_field_goals_made) AS total_field_goals_made,
        SUM(total_field_goals_attempted) AS total_field_goals_attempted,
        SUM(total_three_pointers_made) AS total_three_pointers_made,
        SUM(total_three_pointers_attempted) AS total_three_pointers_attempted,
        SUM(total_free_throws_made) AS total_free_throws_made,
        SUM(total_free_throws_attempted) AS total_free_throws_attempted,
        SUM(ts_points) AS ts_points,
        SUM(ts_field_goals_attempted) AS ts_field_goals_attempted,
        SUM(ts_free_throws_attempted) AS ts_free_throws_attempted,
        SUM(efg_three_pointers_made) AS efg_three_pointers_made
    FROM
        season_stats
    WHERE
        season_start_year >= {{ nba_first_complete_season() }}
    GROUP BY
        person_id, game_type
),

before_coverage AS (
    SELECT DISTINCT
        person_id,
        game_type
    FROM
        season_stats
    WHERE
        season_start_year < {{ nba_first_complete_season() }}
)

SELECT
    c.person_id,
    c.first_name,
    c.last_name,
    c.game_type,
    p.is_guard,
    p.is_forward,
    p.is_center,
    p.draft_year,
    p.height_inches,
    b.person_id IS NOT NULL AS has_games_before_coverage,
    c.seasons_played,
    c.first_season_start_year,
    c.last_season_start_year,
    c.first_game_date,
    c.last_game_date,
    c.games_played,
    c.total_minutes,
    c.total_points,
    c.total_rebounds,
    c.total_assists,
    c.total_steals,
    c.total_blocks,
    c.total_turnovers,
    c.total_field_goals_made,
    c.total_field_goals_attempted,
    c.total_three_pointers_made,
    c.total_three_pointers_attempted,
    c.total_free_throws_made,
    c.total_free_throws_attempted,
    c.ts_points,
    c.ts_field_goals_attempted,
    c.ts_free_throws_attempted,
    c.efg_three_pointers_made,
    c.total_points::DOUBLE / NULLIF(c.games_played, 0) AS points_per_game,
    c.total_rebounds::DOUBLE / NULLIF(c.games_played, 0) AS rebounds_per_game,
    c.total_assists::DOUBLE / NULLIF(c.games_played, 0) AS assists_per_game,
    c.total_field_goals_made::DOUBLE / NULLIF(c.total_field_goals_attempted, 0) AS career_field_goal_pct,
    c.total_three_pointers_made::DOUBLE / NULLIF(c.total_three_pointers_attempted, 0)
        AS career_three_point_pct,
    c.total_free_throws_made::DOUBLE / NULLIF(c.total_free_throws_attempted, 0) AS career_free_throw_pct,
    {{ nba_ts('c.ts_points', 'c.ts_field_goals_attempted', 'c.ts_free_throws_attempted') }}
        AS career_true_shooting_pct
FROM
    career c
LEFT JOIN
    players p
    USING (person_id)
LEFT JOIN
    before_coverage b
    USING (person_id, game_type)
ORDER BY
    c.game_type DESC, c.total_points DESC
