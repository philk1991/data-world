-- Staged NBA franchise histories. One row per franchise era.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_nba', 'raw_nba_team_histories') }}
)

SELECT
    teamId AS team_id,
    teamCity AS team_city,
    teamName AS team_name,
    teamAbbrev AS team_abbrev,
    seasonFounded AS season_founded,
    seasonActiveTill AS season_active_till,
    league,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
