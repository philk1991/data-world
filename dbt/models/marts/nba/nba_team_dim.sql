-- Conformed franchise dimension: one row per team_id carrying its current
-- identity, with relocation/rename history rolled up from the franchise eras.
-- stg_nba_team_histories holds one row per franchise era (team_id, season_founded);
-- the window aggregates run over every era, then QUALIFY keeps the latest one.
WITH histories AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_histories') }}
)

SELECT
    team_id,
    team_city AS current_team_city,
    team_name AS current_team_name,
    team_city || ' ' || team_name AS current_full_name,
    team_abbrev AS current_team_abbrev,
    league AS current_league,
    season_founded AS current_era_season_founded,
    season_active_till AS current_era_active_till,
    MIN(season_founded) OVER (PARTITION BY team_id) AS franchise_first_season,
    COUNT(*) OVER (PARTITION BY team_id) AS franchise_era_count,
    COUNT(*) OVER (PARTITION BY team_id) > 1 AS has_relocated_or_renamed
FROM
    histories
QUALIFY ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY season_founded DESC) = 1
ORDER BY
    team_id
