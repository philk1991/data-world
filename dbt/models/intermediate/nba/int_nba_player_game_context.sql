-- One row per player per competitive game, with the team's and opponent's
-- counts for that game and the per-game "opportunity" denominators every
-- team-context player rate is built from (macros/nba_metrics.sql). A rate over
-- any period is SUM(numerator) / SUM(opportunity), so games, stints, seasons and
-- careers all aggregate the same way. Each opportunity is null whenever its
-- numerator or any input is null, so the two sums always cover the same games.
-- team_player_minutes is the team's summed player minutes for the game: player
-- minutes are truncated to whole minutes before 2024-25, so using the same
-- source on both sides keeps the five floor shares summing to 5.
WITH player_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_games') }}
),

team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

-- Transform
with_team_minutes AS (
    SELECT
        *,
        SUM(minutes_played) OVER (PARTITION BY game_id, team_id) AS team_player_minutes
    FROM
        player_games
),

joined AS (
    SELECT
        p.game_id,
        p.person_id,
        p.team_id,
        p.opponent_team_id,
        p.season_start_year,
        p.game_type,
        p.game_date,
        p.is_home,
        p.is_win,
        p.is_starter,
        p.minutes_played,
        p.team_player_minutes,
        p.points,
        p.field_goals_made,
        p.field_goals_attempted,
        CASE WHEN p.season_start_year < 1979 THEN 0 ELSE p.three_pointers_made END AS three_pointers_made,
        CASE WHEN p.season_start_year < 1979 THEN 0 ELSE p.three_pointers_attempted END AS three_pointers_attempted,
        p.free_throws_made,
        p.free_throws_attempted,
        p.rebounds_offensive,
        p.rebounds_defensive,
        p.rebounds_total,
        p.assists,
        p.steals,
        p.blocks,
        p.turnovers,
        p.fouls_personal,
        t.has_full_box,
        t.points AS team_points,
        t.field_goals_made AS team_field_goals_made,
        t.field_goals_attempted AS team_field_goals_attempted,
        t.three_pointers_made AS team_three_pointers_made,
        t.free_throws_made AS team_free_throws_made,
        t.free_throws_attempted AS team_free_throws_attempted,
        t.rebounds_offensive AS team_rebounds_offensive,
        t.rebounds_defensive AS team_rebounds_defensive,
        t.rebounds_total AS team_rebounds_total,
        t.assists AS team_assists,
        t.steals AS team_steals,
        t.blocks AS team_blocks,
        t.turnovers AS team_turnovers,
        t.fouls_personal AS team_fouls_personal,
        t.opp_points,
        t.opp_field_goals_made,
        t.opp_field_goals_attempted,
        t.opp_three_pointers_attempted,
        t.opp_free_throws_made,
        t.opp_free_throws_attempted,
        t.opp_rebounds_offensive,
        t.opp_rebounds_defensive,
        t.opp_rebounds_total,
        t.opp_turnovers,
        CASE WHEN t.has_full_box AND t.season_start_year >= 1973 THEN t.possessions END AS team_possessions,
        {{ nba_on_court_share('p.minutes_played', 'p.team_player_minutes') }} AS on_court_share
    FROM
        with_team_minutes p
    LEFT JOIN
        team_games t
        USING (game_id, team_id)
)

SELECT
    *,
    -- Usage: plays used / on-court share of team plays.
    field_goals_attempted + 0.44 * free_throws_attempted + turnovers AS usage_plays,
    CASE
        WHEN turnovers IS NOT NULL AND field_goals_attempted IS NOT NULL AND free_throws_attempted IS NOT NULL
            THEN on_court_share * (team_field_goals_attempted + 0.44 * team_free_throws_attempted + team_turnovers)
    END AS usage_opportunity,
    -- Assist %: teammates' field goals made while on the floor.
    CASE WHEN assists IS NOT NULL THEN on_court_share * team_field_goals_made - field_goals_made END
        AS assist_opportunity,
    -- Rebound shares: rebounds available while on the floor.
    CASE
        WHEN rebounds_offensive IS NOT NULL
            THEN on_court_share * (team_rebounds_offensive + opp_rebounds_defensive)
    END AS offensive_rebound_opportunity,
    CASE
        WHEN rebounds_defensive IS NOT NULL
            THEN on_court_share * (team_rebounds_defensive + opp_rebounds_offensive)
    END AS defensive_rebound_opportunity,
    CASE
        WHEN rebounds_total IS NOT NULL
            THEN on_court_share * (team_rebounds_total + opp_rebounds_total)
    END AS rebound_opportunity,
    -- Steal %: opponent possessions while on the floor; block %: opponent two-point attempts.
    CASE WHEN steals IS NOT NULL THEN on_court_share * team_possessions END AS steal_opportunity,
    CASE
        WHEN blocks IS NOT NULL
            THEN on_court_share * (opp_field_goals_attempted - opp_three_pointers_attempted)
    END AS block_opportunity,
    -- Possessions the player was on the floor for (per-100 denominator).
    on_court_share * team_possessions AS player_possessions,
    {{
        nba_game_score(
            'points', 'field_goals_made', 'field_goals_attempted', 'free_throws_made', 'free_throws_attempted',
            'rebounds_offensive', 'rebounds_defensive', 'steals', 'assists', 'blocks', 'fouls_personal', 'turnovers'
        )
    }} AS game_score
FROM
    joined
