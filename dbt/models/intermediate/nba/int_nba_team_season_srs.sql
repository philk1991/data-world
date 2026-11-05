-- One row per team per regular season: Simple Rating System (SRS) and strength
-- of schedule (SOS), Basketball-Reference's definition, for every season.
-- SRS solves SRS[t] = MOV[t] + mean(SRS of each opponent t played, per game) by
-- iteration from SRS = MOV, re-centring on a games-weighted league mean of 0
-- after each step, until no team moves by 1e-6 (or 500 iterations).
-- SOS = SRS - MOV.
-- Each season's state is one row of lists (team i's rating at list index i), so
-- the recursive CTE updates every team at once. Regular season only: playoff
-- and play-in schedules are brackets or disconnected pairs, where the
-- iteration oscillates instead of converging.
WITH RECURSIVE team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

-- Transform
margins AS (
    SELECT
        season_start_year,
        team_id,
        opponent_team_id,
        points - opp_points AS margin
    FROM
        team_games
    WHERE
        game_type = 'Regular Season'
        AND points IS NOT NULL
        AND opp_points IS NOT NULL
),

team_mov AS (
    SELECT
        season_start_year,
        team_id,
        COUNT(*) AS games,
        AVG(margin) AS mov
    FROM
        margins
    GROUP BY
        season_start_year, team_id
),

indexed AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY season_start_year ORDER BY team_id) AS team_index
    FROM
        team_mov
),

-- Each team's opponents, one list entry per game, as list indexes.
opponents AS (
    SELECT
        m.season_start_year,
        m.team_id,
        LIST(o.team_index) AS opponent_indexes
    FROM
        margins m
    INNER JOIN
        indexed o
        ON
            m.season_start_year = o.season_start_year
            AND m.opponent_team_id = o.team_id
    GROUP BY
        m.season_start_year, m.team_id
),

seasons AS (
    SELECT
        i.season_start_year,
        LIST(i.team_id ORDER BY i.team_index) AS team_ids,
        LIST(i.games ORDER BY i.team_index) AS games,
        LIST(i.mov ORDER BY i.team_index) AS movs,
        LIST(o.opponent_indexes ORDER BY i.team_index) AS opponent_indexes
    FROM
        indexed i
    INNER JOIN
        opponents o
        USING (season_start_year, team_id)
    GROUP BY
        i.season_start_year
),

solve (season_start_year, team_ids, games, movs, opponent_indexes, srs, iteration, max_change) AS (
    SELECT
        season_start_year,
        team_ids,
        games,
        movs,
        opponent_indexes,
        movs AS srs,
        0 AS iteration,
        1e9::DOUBLE AS max_change
    FROM
        seasons

    UNION ALL

    SELECT
        season_start_year,
        team_ids,
        games,
        movs,
        opponent_indexes,
        centred AS srs,
        iteration + 1 AS iteration,
        LIST_MAX(LIST_TRANSFORM(LIST_ZIP(centred, srs), p -> ABS(p[1] - p[2]))) AS max_change
    FROM
        (
            SELECT
                *,
                LIST_TRANSFORM(
                    raw,
                    x -> x - LIST_SUM(LIST_TRANSFORM(LIST_ZIP(raw, games), p -> p[1] * p[2])) / LIST_SUM(games)
                ) AS centred
            FROM
                (
                    SELECT
                        *,
                        LIST_TRANSFORM(
                            LIST_ZIP(movs, opponent_indexes),
                            p -> p[1] + LIST_AVG(LIST_TRANSFORM(p[2], j -> srs[j]))
                        ) AS raw
                    FROM
                        solve
                    WHERE
                        max_change >= 1e-6
                        AND iteration < 500
                ) stepped
        ) centred_step
),

converged AS (
    SELECT *
    FROM
        solve
    QUALIFY
        iteration = MAX(iteration) OVER (PARTITION BY season_start_year)
),

unnested AS (
    SELECT
        season_start_year,
        iteration AS srs_iterations,
        max_change < 1e-6 AS is_srs_converged,
        UNNEST(team_ids) AS team_id,
        UNNEST(movs) AS mov,
        UNNEST(srs) AS srs
    FROM
        converged
)

-- Rounded to 4 decimals: the solve stops within 1e-6, so further digits are noise.
SELECT
    season_start_year,
    team_id,
    ROUND(mov, 4) AS mov,
    ROUND(srs, 4) AS srs,
    ROUND(srs - mov, 4) AS sos,
    srs_iterations,
    is_srs_converged
FROM
    unnested
