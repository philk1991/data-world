-- One row per player summarising advanced career efficiency, enriched with bio.
-- Sourced from the advanced player box scores (available since ~1996), so the
-- careers of earlier players are not represented. Rate metrics are minutes-weighted
-- (sum(metric * minutes) / sum(minutes)) so high-minute games count for more than
-- garbage-time cameos; only games with recorded minutes and advanced data count.
WITH player_advanced AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics_extended') }}
),

players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

weighted AS (
    SELECT
        person_id,
        COUNT(DISTINCT game_id) AS games_with_advanced,
        SUM(minutes_played) AS total_minutes,
        COUNT(CASE WHEN is_double_double THEN 1 END) AS double_doubles,
        COUNT(CASE WHEN is_triple_double THEN 1 END) AS triple_doubles,
        SUM(usage_percentage * minutes_played) AS w_usage,
        SUM(true_shooting_percentage * minutes_played) AS w_true_shooting,
        SUM(effective_field_goal_percentage * minutes_played) AS w_efg,
        SUM(offensive_rating * minutes_played) AS w_offensive_rating,
        SUM(defensive_rating * minutes_played) AS w_defensive_rating,
        SUM(net_rating * minutes_played) AS w_net_rating,
        SUM(assist_percentage * minutes_played) AS w_assist,
        SUM(rebound_percentage * minutes_played) AS w_rebound,
        SUM(player_impact_estimate * minutes_played) AS w_pie
    FROM
        player_advanced
    WHERE
        person_id IS NOT NULL
        AND minutes_played IS NOT NULL
        AND minutes_played > 0
        AND offensive_rating IS NOT NULL
    GROUP BY
        person_id
)

SELECT
    w.person_id,
    p.first_name,
    p.last_name,
    p.is_guard,
    p.is_forward,
    p.is_center,
    w.games_with_advanced,
    ROUND(w.total_minutes / NULLIF(w.games_with_advanced, 0), 1) AS minutes_per_game,
    w.double_doubles,
    w.triple_doubles,
    ROUND(w.w_usage / NULLIF(w.total_minutes, 0), 3) AS usage_pct,
    ROUND(w.w_true_shooting / NULLIF(w.total_minutes, 0), 3) AS true_shooting_pct,
    ROUND(w.w_efg / NULLIF(w.total_minutes, 0), 3) AS effective_field_goal_pct,
    ROUND(w.w_offensive_rating / NULLIF(w.total_minutes, 0), 1) AS offensive_rating,
    ROUND(w.w_defensive_rating / NULLIF(w.total_minutes, 0), 1) AS defensive_rating,
    ROUND(w.w_net_rating / NULLIF(w.total_minutes, 0), 1) AS net_rating,
    ROUND(w.w_assist / NULLIF(w.total_minutes, 0), 3) AS assist_pct,
    ROUND(w.w_rebound / NULLIF(w.total_minutes, 0), 3) AS rebound_pct,
    ROUND(w.w_pie / NULLIF(w.total_minutes, 0), 3) AS player_impact_estimate
FROM
    weighted w
LEFT JOIN
    players p
    USING (person_id)
ORDER BY
    w.triple_doubles DESC, net_rating DESC
