-- Staged NBA player biographies. Casts position/league flags to booleans.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_nba', 'raw_nba_players') }}
)

SELECT
    personId AS person_id,
    firstName AS first_name,
    lastName AS last_name,
    birthDate::DATE AS birth_date,
    school,
    country,
    heightInches AS height_inches,
    bodyWeightLbs AS body_weight_lbs,
    jersey,
    guard = 1 AS is_guard,
    forward = 1 AS is_forward,
    center = 1 AS is_center,
    dleagueFlag = 1 AS is_dleague,
    nbaFlag = 1 AS is_nba,
    gamesPlayedFlag = 1 AS has_games_played,
    draftYear AS draft_year,
    draftRound AS draft_round,
    draftNumber AS draft_number,
    fromYear AS from_year,
    toYear AS to_year,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
