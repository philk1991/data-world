-- Guards source defects the dataset profile found. No team game may have more
-- makes than attempts (some 1959-62 team box scores record only part of the
-- attempts) or more assists than made field goals, and no player's floor share
-- may exceed one full game (some 1951-84 games record minutes for only part of
-- the roster). The share allows 5% above 1 because truncated player minutes make
-- the team total ~235, not 240. Returns each offending row with the rule it breaks.
WITH team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

context AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_game_context') }}
),

violations AS (
    SELECT
        'team game: makes exceed attempts or assists exceed makes' AS rule,
        game_id::VARCHAR || '/' || team_id::VARCHAR AS row_key
    FROM
        team_games
    WHERE
        field_goals_made > field_goals_attempted
        OR three_pointers_made > three_pointers_attempted
        OR free_throws_made > free_throws_attempted
        OR assists > field_goals_made

    UNION ALL

    SELECT
        'player game: floor share above one game' AS rule,
        game_id::VARCHAR || '/' || person_id::VARCHAR AS row_key
    FROM
        context
    WHERE
        on_court_share > 1.05
)

SELECT *
FROM
    violations
