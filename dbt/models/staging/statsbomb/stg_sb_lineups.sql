-- Staged StatsBomb lineup data. One row per player per match.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_statsbomb', 'raw_sb_lineups') }}
)

SELECT
    match_id,
    team_name,
    player_id,
    player_name,
    player_nickname,
    jersey_number,
    country_name,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
