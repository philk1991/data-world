-- One row per player per competitive game played (Regular Season, Play-in
-- Tournament, Playoffs, NBA Cup Final), with the player's team resolved.
-- player_team_id is null in the raw data for tens of thousands of rows (all of
-- 2021-22, a few thousand a season since 2003), so the team falls back to the
-- game's home or away team by is_home. Preseason and All-Star games are excluded.
-- "Played" follows nba_player_game_stats: minutes_played not null. Before
-- 1964-65 most games record every player's minutes as 0, so minutes_played is
-- nulled for any game whose minutes sum to 0 rather than read as zero.
WITH box_scores AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics') }}
),

games AS (
    SELECT *
    FROM
        {{ ref('stg_nba_games') }}
),

-- Transform
played AS (
    SELECT *
    FROM
        box_scores
    WHERE
        person_id IS NOT NULL
        AND minutes_played IS NOT NULL
        AND game_type IN ('Regular Season', 'Play-in Tournament', 'Playoffs', 'NBA Cup Final')
)

SELECT
    b.game_id,
    b.person_id,
    b.season_start_year,
    b.game_type,
    b.game_date,
    COALESCE(
        b.player_team_id,
        CASE WHEN b.is_home THEN g.home_team_id WHEN NOT b.is_home THEN g.away_team_id END
    ) AS team_id,
    COALESCE(
        b.opponent_team_id,
        CASE WHEN b.is_home THEN g.away_team_id WHEN NOT b.is_home THEN g.home_team_id END
    ) AS opponent_team_id,
    b.player_team_id IS NULL AS is_team_inferred,
    b.is_home,
    b.is_win,
    b.starting_position IS NOT NULL AS is_starter,
    CASE
        WHEN SUM(b.minutes_played) OVER (PARTITION BY b.game_id) > 0 THEN b.minutes_played
    END AS minutes_played,
    b.points,
    b.field_goals_made,
    b.field_goals_attempted,
    b.three_pointers_made,
    b.three_pointers_attempted,
    b.free_throws_made,
    b.free_throws_attempted,
    b.rebounds_offensive,
    b.rebounds_defensive,
    b.rebounds_total,
    b.assists,
    b.steals,
    b.blocks,
    b.turnovers,
    b.fouls_personal,
    b.plus_minus_points
FROM
    played b
LEFT JOIN
    games g
    USING (game_id)
