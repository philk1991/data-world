-- Team-season dimension: one row per team per season it played competitive
-- games, carrying the team's identity as of that season (the 2007-08
-- SuperSonics, not today's Thunder). City and name come from the season's team
-- box scores, which never carry two names for one team in a season; the
-- abbreviation comes from the franchise era (stg_nba_team_histories) covering
-- the season. nba_team_dim keeps the current identity.
WITH team_box AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_statistics') }}
),

histories AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_histories') }}
),

-- Transform
team_seasons AS (
    SELECT
        team_id,
        season_start_year,
        ARG_MAX(team_city, game_date) AS team_city,
        ARG_MAX(team_name, game_date) AS team_name
    FROM
        team_box
    -- All-Star games pit exhibition teams (Team LeBron, Stars), not franchises.
    WHERE
        game_type IN {{ nba_competitive_game_types() }}
    GROUP BY
        team_id, season_start_year
)

SELECT
    t.team_id,
    t.season_start_year,
    {{ nba_season_label('t.season_start_year') }} AS season_label,
    t.team_city,
    t.team_name,
    t.team_city || ' ' || t.team_name AS team_full_name,
    h.team_abbrev
FROM
    team_seasons t
LEFT JOIN
    histories h
    ON
        t.team_id = h.team_id
        AND t.season_start_year BETWEEN h.season_founded AND h.season_active_till
QUALIFY
    ROW_NUMBER() OVER (PARTITION BY t.team_id, t.season_start_year ORDER BY h.season_founded DESC) = 1
ORDER BY
    t.season_start_year, t.team_id
