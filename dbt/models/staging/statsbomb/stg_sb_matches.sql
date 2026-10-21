-- Staged StatsBomb match metadata.
-- Derives match_result and goal_difference. Filters to available matches only.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_statsbomb', 'raw_sb_matches') }}
)

SELECT
    match_id,
    match_date::DATE AS match_date,
    kick_off::TIME AS kick_off,
    competition_id,
    competition_name,
    season_id,
    season_name,
    home_team_name,
    away_team_name,
    home_score,
    away_score,
    home_score - away_score AS goal_difference,
    CASE
        WHEN home_score > away_score THEN 'home_win'
        WHEN home_score < away_score THEN 'away_win'
        ELSE 'draw'
    END AS match_result,
    match_status,
    match_week,
    competition_stage,
    stadium_name,
    referee_name,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
WHERE
    match_status = 'available'
