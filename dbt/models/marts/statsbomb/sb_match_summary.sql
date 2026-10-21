-- One row per match with competition context and aggregate event counts.
-- Event counts use conditional aggregation over the event type column.
WITH matches AS (
    SELECT *
    FROM
        {{ ref('stg_sb_matches') }}
),

event_counts AS (
    SELECT
        match_id,
        COUNT(*) AS total_events,
        COUNT(CASE WHEN event_type = 'Shot' THEN 1 END) AS total_shots,
        COUNT(CASE WHEN event_type = 'Pass' THEN 1 END) AS total_passes,
        COUNT(CASE WHEN event_type = 'Dribble' THEN 1 END) AS total_dribbles,
        COUNT(CASE WHEN event_type = 'Pressure' THEN 1 END) AS total_pressures,
        COUNT(CASE WHEN event_type = 'Carry' THEN 1 END) AS total_carries
    FROM
        {{ ref('stg_sb_events') }}
    GROUP BY
        match_id
)

SELECT
    m.match_id,
    m.match_date,
    m.competition_id,
    m.competition_name,
    m.season_id,
    m.season_name,
    m.home_team_name,
    m.away_team_name,
    m.home_score,
    m.away_score,
    m.goal_difference,
    m.match_result,
    m.match_week,
    m.competition_stage,
    m.stadium_name,
    COALESCE(e.total_events, 0) AS total_events,
    COALESCE(e.total_shots, 0) AS total_shots,
    COALESCE(e.total_passes, 0) AS total_passes,
    COALESCE(e.total_dribbles, 0) AS total_dribbles,
    COALESCE(e.total_pressures, 0) AS total_pressures,
    COALESCE(e.total_carries, 0) AS total_carries,
    m.ingested_at
FROM
    matches m
LEFT JOIN
    event_counts e
    USING (match_id)
ORDER BY
    m.match_date DESC
