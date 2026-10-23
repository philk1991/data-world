-- Staged NBA player biographies. Casts position/league flags to booleans.
-- The raw data marks undrafted players with draftYear = -1 (or draftRound = 0,
-- keeping the class year they went undrafted in) and unknown picks with -22;
-- these become nulls, with is_undrafted carrying the distinction. Placeholder
-- birth dates (1900-01-01, 1995-01-01 and a block of April 1905 dates on
-- players who debuted 1946-54) are nulled too.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_nba', 'raw_nba_players') }}
)

SELECT
    personId AS person_id,
    firstName AS first_name,
    lastName AS last_name,
    CASE
        WHEN
            birthDate::DATE IN ('1900-01-01'::DATE, '1995-01-01'::DATE)
            OR birthDate::DATE BETWEEN '1905-04-01'::DATE AND '1905-04-30'::DATE
            THEN NULL
        ELSE birthDate::DATE
    END AS birth_date,
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
    CASE
        WHEN draftYear = -1 OR draftRound = 0 THEN TRUE
        WHEN draftYear IS NOT NULL THEN FALSE
    END AS is_undrafted,
    CASE WHEN draftYear > 0 AND COALESCE(draftRound, -1) != 0 THEN draftYear END AS draft_year,
    CASE WHEN draftRound > 0 THEN draftRound END AS draft_round,
    CASE WHEN draftNumber > 0 THEN draftNumber END AS draft_number,
    fromYear AS from_year,
    toYear AS to_year,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
