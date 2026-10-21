-- Staged StatsBomb competition/season pairs.
-- Minimal transformation: cast ingested_at and pass all columns through cleanly.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_statsbomb', 'raw_sb_competitions') }}
)

SELECT
    competition_id,
    competition_name,
    country_name,
    competition_gender,
    competition_youth,
    competition_international,
    season_id,
    season_name,
    match_available_360,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
