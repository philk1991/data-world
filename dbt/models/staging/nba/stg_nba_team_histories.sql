-- Staged NBA franchise histories. One row per franchise era. The raw
-- abbreviations are space-padded, so they are trimmed.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_nba', 'raw_nba_team_histories') }}
)

SELECT
    teamId AS team_id,
    teamCity AS team_city,
    teamName AS team_name,
    TRIM(teamAbbrev) AS team_abbrev,
    seasonFounded AS season_founded,
    seasonActiveTill AS season_active_till,
    league,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
