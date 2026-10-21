-- Aggregated player statistics across all StatsBomb open data matches.
-- One row per (player_id, team) — a player who transferred between clubs will
-- appear as multiple rows, one per team they played for in the dataset.
WITH events AS (
    SELECT *
    FROM
        {{ ref('stg_sb_events') }}
),

lineups AS (
    SELECT *
    FROM
        {{ ref('stg_sb_lineups') }}
),

player_events AS (
    SELECT
        player_id,
        player_name,
        team,
        COUNT(DISTINCT match_id) AS matches_in_events,
        COUNT(*) AS total_events,
        COUNT(CASE WHEN event_type = 'Pass' THEN 1 END) AS total_passes,
        COUNT(CASE WHEN event_type = 'Shot' THEN 1 END) AS total_shots,
        COUNT(CASE WHEN event_type = 'Dribble' THEN 1 END) AS total_dribbles,
        COUNT(CASE WHEN event_type = 'Pressure' THEN 1 END) AS total_pressures,
        COUNT(CASE WHEN event_type = 'Carry' THEN 1 END) AS total_carries,
        ROUND(SUM(COALESCE(duration, 0)) / 60.0, 2) AS total_duration_minutes
    FROM
        events
    WHERE
        player_id IS NOT NULL
    GROUP BY
        player_id, player_name, team
),

player_appearances AS (
    SELECT
        player_id,
        team_name AS team,
        COUNT(DISTINCT match_id) AS lineup_appearances,
        MAX(country_name) AS country_name
    FROM
        lineups
    GROUP BY
        player_id, team_name
)

SELECT
    pe.player_id,
    pe.player_name,
    pe.team,
    pa.country_name,
    COALESCE(pa.lineup_appearances, 0) AS lineup_appearances,
    pe.matches_in_events,
    pe.total_events,
    pe.total_passes,
    pe.total_shots,
    pe.total_dribbles,
    pe.total_pressures,
    pe.total_carries,
    pe.total_duration_minutes
FROM
    player_events pe
LEFT JOIN
    player_appearances pa
    ON
        pe.player_id = pa.player_id
        AND pe.team = pa.team
ORDER BY
    pe.total_shots DESC
