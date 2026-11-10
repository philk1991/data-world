-- One row per player per season per game type (Regular Season, Playoffs, etc.)
-- of traditional box score totals, per-game averages and shooting splits,
-- enriched with bio. Built on int_nba_player_games (the same played games as
-- nba_player_game_stats, with the team resolved). A player traded mid-season is
-- combined into a single row per game type; primary_team_id is the team they
-- played the most games for (ties: most minutes, then the lower team id), the
-- one rule nba_player_season_advanced also reads from here.
-- Made shots are only counted in games where the matching attempts were
-- recorded, so the shooting percentages compare like with like. The ts_* and
-- efg_* columns are the additive inputs for true shooting and effective field
-- goal percentage, summed over the same games as nba_player_stint_advanced, so
-- Cube can divide them at any grain (plans/adr/0002-dbt-cube-boundary.md).
-- team_games_played and is_qualified make per-game leaderboards fair in short
-- seasons (2019-20, 2020-21, lockouts), where a fixed games-played minimum is
-- biased.
WITH player_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_games') }}
),

players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

team_box AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_statistics') }}
),

-- Transform
team_games AS (
    SELECT
        team_id,
        season_start_year,
        game_type,
        COUNT(DISTINCT game_id) AS team_games_played
    FROM
        team_box
    GROUP BY
        team_id, season_start_year, game_type
),

-- Fallback for players with no primary team: the most games any team played.
league_games AS (
    SELECT
        season_start_year,
        game_type,
        MAX(team_games_played) AS max_team_games_played
    FROM
        team_games
    GROUP BY
        season_start_year, game_type
),

player_teams AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        team_id,
        COUNT(*) AS games,
        COALESCE(SUM(minutes_played), 0) AS minutes
    FROM
        player_games
    GROUP BY
        person_id, season_start_year, game_type, team_id
),

-- Box-score name for players with no bio record.
box_score_names AS (
    SELECT
        person_id,
        ARG_MAX(first_name, game_date) AS first_name,
        ARG_MAX(last_name, game_date) AS last_name
    FROM
        player_games
    GROUP BY
        person_id
),

primary_teams AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        team_id AS primary_team_id
    FROM
        player_teams
    QUALIFY
        ROW_NUMBER() OVER (
            PARTITION BY person_id, season_start_year, game_type
            ORDER BY games DESC, minutes DESC, team_id ASC
        ) = 1
),

season_totals AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        COUNT(*) AS games_played,
        MIN(game_date) AS first_game_date,
        MAX(game_date) AS last_game_date,
        SUM(minutes_played) AS total_minutes,
        SUM(points) AS total_points,
        SUM(rebounds_total) AS total_rebounds,
        SUM(assists) AS total_assists,
        SUM(steals) AS total_steals,
        SUM(blocks) AS total_blocks,
        SUM(turnovers) AS total_turnovers,
        SUM(field_goals_made) FILTER (WHERE field_goals_attempted IS NOT NULL) AS total_field_goals_made,
        SUM(field_goals_attempted) AS total_field_goals_attempted,
        SUM(three_pointers_made) FILTER (WHERE three_pointers_attempted IS NOT NULL) AS total_three_pointers_made,
        SUM(three_pointers_attempted) AS total_three_pointers_attempted,
        SUM(free_throws_made) FILTER (WHERE free_throws_attempted IS NOT NULL) AS total_free_throws_made,
        SUM(free_throws_attempted) AS total_free_throws_attempted,
        -- True shooting inputs: games with both attempt counts recorded.
        SUM(points) FILTER (
            WHERE field_goals_attempted IS NOT NULL AND free_throws_attempted IS NOT NULL
        ) AS ts_points,
        SUM(field_goals_attempted) FILTER (WHERE free_throws_attempted IS NOT NULL) AS ts_field_goals_attempted,
        SUM(free_throws_attempted) FILTER (WHERE field_goals_attempted IS NOT NULL) AS ts_free_throws_attempted,
        -- Effective field goal input: threes made in games with field goal attempts recorded
        -- (0 before the line existed), to pair with total_field_goals_made and _attempted.
        SUM(COALESCE(three_pointers_made, 0)) FILTER (WHERE field_goals_attempted IS NOT NULL)
            AS efg_three_pointers_made
    FROM
        player_games
    GROUP BY
        person_id, season_start_year, game_type
)

SELECT
    s.person_id,
    COALESCE(p.first_name, n.first_name) AS first_name,
    COALESCE(p.last_name, n.last_name) AS last_name,
    s.season_start_year,
    {{ nba_season_label('s.season_start_year') }} AS season_label,
    s.game_type,
    s.game_type IN {{ nba_competitive_game_types() }} AS is_competitive,
    pt.primary_team_id,
    s.games_played,
    COALESCE(tg.team_games_played, lg.max_team_games_played) AS team_games_played,
    -- The 58-of-82 per-game minimum, scaled to the games the team actually played.
    -- Only defined for the regular season.
    CASE
        WHEN s.game_type = 'Regular Season'
            THEN s.games_played >= 0.7 * COALESCE(tg.team_games_played, lg.max_team_games_played)
    END AS is_qualified,
    s.first_game_date,
    s.last_game_date,
    ROUND(s.total_minutes, 1) AS total_minutes,
    s.total_points,
    s.total_rebounds,
    s.total_assists,
    s.total_steals,
    s.total_blocks,
    s.total_turnovers,
    s.total_field_goals_made,
    s.total_field_goals_attempted,
    s.total_three_pointers_made,
    s.total_three_pointers_attempted,
    s.total_free_throws_made,
    s.total_free_throws_attempted,
    s.ts_points,
    s.ts_field_goals_attempted,
    s.ts_free_throws_attempted,
    s.efg_three_pointers_made,
    ROUND(s.total_points::DOUBLE / NULLIF(s.games_played, 0), 1) AS points_per_game,
    ROUND(s.total_rebounds::DOUBLE / NULLIF(s.games_played, 0), 1) AS rebounds_per_game,
    ROUND(s.total_assists::DOUBLE / NULLIF(s.games_played, 0), 1) AS assists_per_game,
    ROUND(s.total_field_goals_made::DOUBLE / NULLIF(s.total_field_goals_attempted, 0), 3) AS field_goal_pct,
    ROUND(s.total_three_pointers_made::DOUBLE / NULLIF(s.total_three_pointers_attempted, 0), 3) AS three_point_pct,
    ROUND(s.total_free_throws_made::DOUBLE / NULLIF(s.total_free_throws_attempted, 0), 3) AS free_throw_pct
FROM
    season_totals s
LEFT JOIN
    primary_teams pt
    USING (person_id, season_start_year, game_type)
LEFT JOIN
    players p
    USING (person_id)
LEFT JOIN
    box_score_names n
    USING (person_id)
LEFT JOIN
    team_games tg
    ON
        pt.primary_team_id = tg.team_id
        AND s.season_start_year = tg.season_start_year
        AND s.game_type = tg.game_type
LEFT JOIN
    league_games lg
    ON
        s.season_start_year = lg.season_start_year
        AND s.game_type = lg.game_type
ORDER BY
    s.season_start_year DESC, s.total_points DESC
