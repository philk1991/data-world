-- Reference check from the brief's section 10 fixture: Basketball-Reference
-- gives LeBron James's 2008-09 regular season PProd 2345.9 and TotPoss 1928.1
-- (individual offensive rating 121.7) and individual defensive rating 99.1.
-- Player minutes here are truncated to whole minutes, so the inputs differ
-- slightly; the ratings must still land within 0.3. Returns the row if not.
WITH season_advanced AS (
    SELECT *
    FROM
        {{ ref('nba_player_season_advanced') }}
)

SELECT
    person_id,
    individual_offensive_rating,
    individual_defensive_rating
FROM
    season_advanced
WHERE
    person_id = 2544
    AND season_start_year = 2008
    AND game_type = 'Regular Season'
    AND (
        ABS(individual_offensive_rating - 121.7) > 0.3
        OR ABS(individual_defensive_rating - 99.1) > 0.3
        OR individual_offensive_rating IS NULL
    )
