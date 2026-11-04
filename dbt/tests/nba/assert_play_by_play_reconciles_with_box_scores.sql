-- The play-by-play should agree with the box scores it was scored from. A few
-- hundred player-games and a few dozen games differ in the source itself (late
-- stat corrections, a missing or duplicated event), so this checks rates, not
-- exact equality: it fails when more than 0.5% of player-games have different
-- points or field goal attempts, or more than 0.5% of games end on a different
-- score. Each returned row is one check over its threshold.
WITH play_by_play AS (
    SELECT *
    FROM
        {{ ref('stg_nba_play_by_play') }}
),

box_scores AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics') }}
),

games AS (
    SELECT *
    FROM
        {{ ref('stg_nba_games') }}
),

player_games AS (
    SELECT
        game_id,
        person_id,
        SUM(points_scored) AS points,
        COUNT(*) FILTER (WHERE event_type = 'field_goal') AS field_goals_attempted
    FROM
        play_by_play
    WHERE
        person_id IS NOT NULL
    GROUP BY
        game_id, person_id
),

final_scores AS (
    SELECT
        game_id,
        MAX_BY(score_home, event_order) AS score_home,
        MAX_BY(score_away, event_order) AS score_away
    FROM
        play_by_play
    GROUP BY
        game_id
),

checks AS (
    SELECT
        'player points or FGA differ from the box score' AS check_name,
        AVG((p.points != b.points OR p.field_goals_attempted != b.field_goals_attempted)::INTEGER) AS mismatch_rate
    FROM
        player_games p
    INNER JOIN
        box_scores b
        USING (game_id, person_id)
    WHERE
        b.minutes_played IS NOT NULL

    UNION ALL

    SELECT
        'final score differs from the game record' AS check_name,
        AVG((f.score_home != g.home_score OR f.score_away != g.away_score)::INTEGER) AS mismatch_rate
    FROM
        final_scores f
    INNER JOIN
        games g
        USING (game_id)
)

SELECT *
FROM
    checks
WHERE
    mismatch_rate > 0.005
