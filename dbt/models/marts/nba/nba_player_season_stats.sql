-- One row per player per season per game type (Regular Season, Playoffs, etc.)
-- of traditional box score totals, per-game averages and shooting splits,
-- enriched with bio. Season comes from the game id (see macros/nba_game_id.sql).
-- A player traded mid-season is combined into a single row per game type;
-- primary_team_id is the team they played the most games for. Only games
-- actually played (minutes_played not null) count.
-- Made shots are only counted in games where the matching attempts were recorded,
-- so the shooting percentages compare like with like. team_games_played and
-- is_qualified make per-game leaderboards fair in short seasons (2019-20, 2020-21,
-- lockouts), where a fixed games-played minimum is biased.
WITH box_scores AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics') }}
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

seasoned AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        player_team_id,
        game_id,
        points,
        rebounds_total,
        assists,
        steals,
        blocks,
        turnovers,
        field_goals_made,
        field_goals_attempted,
        three_pointers_made,
        three_pointers_attempted,
        free_throws_made,
        free_throws_attempted
    FROM
        box_scores
    WHERE
        person_id IS NOT NULL
        AND minutes_played IS NOT NULL
        AND game_date IS NOT NULL
        AND game_type IS NOT NULL
),

season_totals AS (
    SELECT
        person_id,
        season_start_year,
        game_type,
        MODE(player_team_id) AS primary_team_id,
        COUNT(DISTINCT game_id) AS games_played,
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
        SUM(free_throws_attempted) AS total_free_throws_attempted
    FROM
        seasoned
    GROUP BY
        person_id, season_start_year, game_type
)

SELECT
    s.person_id,
    p.first_name,
    p.last_name,
    s.season_start_year,
    s.season_start_year::VARCHAR || '-'
    || RIGHT((s.season_start_year + 1)::VARCHAR, 2) AS season_label,
    s.game_type,
    s.primary_team_id,
    s.games_played,
    COALESCE(tg.team_games_played, lg.max_team_games_played) AS team_games_played,
    -- The 58-of-82 per-game minimum, scaled to the games the team actually played.
    -- Only defined for the regular season.
    CASE
        WHEN s.game_type = 'Regular Season'
            THEN s.games_played >= 0.7 * COALESCE(tg.team_games_played, lg.max_team_games_played)
    END AS is_qualified,
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
    ROUND(s.total_points::DOUBLE / NULLIF(s.games_played, 0), 1) AS points_per_game,
    ROUND(s.total_rebounds::DOUBLE / NULLIF(s.games_played, 0), 1) AS rebounds_per_game,
    ROUND(s.total_assists::DOUBLE / NULLIF(s.games_played, 0), 1) AS assists_per_game,
    ROUND(
        s.total_field_goals_made::DOUBLE
        / NULLIF(s.total_field_goals_attempted, 0), 3
    ) AS field_goal_pct,
    ROUND(
        s.total_three_pointers_made::DOUBLE
        / NULLIF(s.total_three_pointers_attempted, 0), 3
    ) AS three_point_pct,
    ROUND(
        s.total_free_throws_made::DOUBLE
        / NULLIF(s.total_free_throws_attempted, 0), 3
    ) AS free_throw_pct
FROM
    season_totals s
LEFT JOIN
    players p
    USING (person_id)
LEFT JOIN
    team_games tg
    ON
        s.primary_team_id = tg.team_id
        AND s.season_start_year = tg.season_start_year
        AND s.game_type = tg.game_type
LEFT JOIN
    league_games lg
    ON
        s.season_start_year = lg.season_start_year
        AND s.game_type = lg.game_type
ORDER BY
    s.season_start_year DESC, s.total_points DESC
