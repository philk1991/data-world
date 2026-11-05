-- Player points should add up to the team's score. Early box scores are
-- incomplete in the source, so the threshold is per era: at least 97% of team
-- games before 1983-84 and 99% from then on. Each returned row is one era over
-- its threshold.
WITH team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

player_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_games') }}
),

player_points AS (
    SELECT
        game_id,
        team_id,
        SUM(points) AS points
    FROM
        player_games
    GROUP BY
        game_id, team_id
),

checks AS (
    SELECT
        t.season_start_year >= 1983 AS is_complete_era,
        AVG((p.points IS NOT DISTINCT FROM t.points)::INTEGER) AS match_rate
    FROM
        team_games t
    LEFT JOIN
        player_points p
        USING (game_id, team_id)
    GROUP BY
        t.season_start_year >= 1983
)

SELECT *
FROM
    checks
WHERE
    match_rate < CASE WHEN is_complete_era THEN 0.99 ELSE 0.97 END
