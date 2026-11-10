-- In every finished season from 1954-55, each team played the same number of
-- Regular Season games, unless the season is a known exception below. A new
-- failure means games went missing upstream (or a new real exception needs
-- adding, with its reason). Returns each team-season off the season's usual
-- count.
WITH seasons AS (
    SELECT *
    FROM
        {{ ref('nba_seasons_dim') }}
),

summaries AS (
    SELECT *
    FROM
        {{ ref('nba_team_season_summary') }}
),

known_exceptions AS (
    SELECT *
    FROM
        (
            VALUES
            -- A few teams have 73-74 games: the source counts extra games (likely
            -- division tiebreakers) as Regular Season.
            (1955, 'extra games, likely tiebreakers'),
            (1956, 'extra games, likely tiebreakers'),
            -- Celtics at Pacers was cancelled after the Boston Marathon bombing.
            (2012, 'one game cancelled'),
            -- The season was cut short by COVID-19; teams finished on 64-75 games.
            (2019, 'COVID-19 shortened season'),
            -- Upstream gap: 4 games missing from the Kaggle source, 2 more recorded 0-0
            -- and dropped (plans/nba-staff-ae-project.md, finding 5). Remove when fixed.
            (2024, 'upstream data gap')
        ) AS t (season_start_year, reason)  -- noqa: AL01, AL05
),

closed AS (
    SELECT
        s.season_start_year,
        s.team_id,
        s.games_played,
        MODE(s.games_played) OVER (PARTITION BY s.season_start_year) AS usual_games
    FROM
        summaries s
    INNER JOIN
        seasons d
        USING (season_start_year)
    WHERE
        d.coverage_tier = 'complete'
)

SELECT
    c.season_start_year,
    c.team_id,
    c.games_played,
    c.usual_games
FROM
    closed c
LEFT JOIN
    known_exceptions k
    USING (season_start_year)
WHERE
    c.games_played <> c.usual_games
    AND k.season_start_year IS NULL
