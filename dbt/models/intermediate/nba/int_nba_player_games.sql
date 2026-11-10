-- One row per player per game played, every game type, with the player's team
-- resolved. is_competitive marks the Regular Season, Play-in Tournament, Playoffs
-- and NBA Cup Final; the team-context models keep only those, while the player
-- game and season marts keep preseason and All-Star games too.
-- player_team_id is null in the raw data for tens of thousands of rows (all of
-- 2021-22, a few thousand a season since 2003), so the team falls back to the
-- game's home or away team by is_home.
-- "Played" means minutes_played is not null (and the game has a date and a known
-- type). Before 1964-65 most games record every player's minutes as 0, so
-- minutes_played is nulled for any game whose minutes sum to 0 rather than read
-- as zero.
-- A shooting pair with more makes than attempts is impossible (71 free-throw and
-- 25 field-goal rows, mostly before 1984) and is nulled, so rates never pass 1.
-- Double-doubles and triple-doubles are counted from the box score here, the one
-- definition every NBA mart uses.
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
        AND game_date IS NOT NULL
        AND game_type IS NOT NULL
),

resolved AS (
    SELECT
        b.game_id,
        b.person_id,
        b.first_name,
        b.last_name,
        b.season_start_year,
        b.game_type,
        b.game_type IN {{ nba_competitive_game_types() }} AS is_competitive,
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
        b.starting_position,
        CASE
            WHEN SUM(b.minutes_played) OVER (PARTITION BY b.game_id) > 0 THEN b.minutes_played
        END AS minutes_played,
        b.points,
        CASE WHEN b.field_goals_made > b.field_goals_attempted THEN NULL ELSE b.field_goals_made END
            AS field_goals_made,
        CASE WHEN b.field_goals_made > b.field_goals_attempted THEN NULL ELSE b.field_goals_attempted END
            AS field_goals_attempted,
        CASE WHEN b.three_pointers_made > b.three_pointers_attempted THEN NULL ELSE b.three_pointers_made END
            AS three_pointers_made,
        CASE WHEN b.three_pointers_made > b.three_pointers_attempted THEN NULL ELSE b.three_pointers_attempted END
            AS three_pointers_attempted,
        CASE WHEN b.free_throws_made > b.free_throws_attempted THEN NULL ELSE b.free_throws_made END
            AS free_throws_made,
        CASE WHEN b.free_throws_made > b.free_throws_attempted THEN NULL ELSE b.free_throws_attempted END
            AS free_throws_attempted,
        b.rebounds_offensive,
        b.rebounds_defensive,
        b.rebounds_total,
        b.assists,
        b.steals,
        b.blocks,
        b.turnovers,
        b.fouls_personal,
        b.plus_minus_points,
        -- Categories in double figures among points, rebounds, assists, steals and blocks.
        (b.points >= 10)::INTEGER
        + COALESCE((b.rebounds_total >= 10)::INTEGER, 0)
        + COALESCE((b.assists >= 10)::INTEGER, 0)
        + COALESCE((b.steals >= 10)::INTEGER, 0)
        + COALESCE((b.blocks >= 10)::INTEGER, 0) AS double_digit_categories
    FROM
        played b
    LEFT JOIN
        games g
        USING (game_id)
)

SELECT
    * EXCLUDE (double_digit_categories),
    COALESCE(double_digit_categories >= 2, FALSE) AS is_double_double,
    COALESCE(double_digit_categories >= 3, FALSE) AS is_triple_double
FROM
    resolved
