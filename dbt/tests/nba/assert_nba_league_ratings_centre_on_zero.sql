-- League net rating and SRS centre on 0 each regular season: the
-- possession-weighted mean net rating (over seasons where every game had a full
-- box) and the games-weighted mean SRS must both be within 0.05.
WITH profile AS (
    SELECT *
    FROM
        {{ ref('nba_team_advanced_profile') }}
),

srs AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_season_srs') }}
),

team_srs AS (
    SELECT
        s.season_start_year,
        s.srs,
        p.games_played
    FROM
        srs s
    INNER JOIN
        profile p
        ON
            s.team_id = p.team_id
            AND s.season_start_year = p.season_start_year
            AND p.game_type = 'Regular Season'
),

checks AS (
    SELECT
        season_start_year,
        'net rating' AS metric,
        SUM(net_rating * possessions) / SUM(possessions) AS weighted_mean
    FROM
        profile
    WHERE
        game_type = 'Regular Season'
        AND season_start_year >= 1983
    GROUP BY
        season_start_year

    UNION ALL

    SELECT
        season_start_year,
        'srs' AS metric,
        SUM(srs * games_played) / SUM(games_played) AS weighted_mean
    FROM
        team_srs
    GROUP BY
        season_start_year
)

SELECT *
FROM
    checks
WHERE
    ABS(weighted_mean) > 0.05
