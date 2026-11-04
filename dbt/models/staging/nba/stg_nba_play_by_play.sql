-- Staged play-by-play. One row per game event (game_id, action_number), 1996-97 onward.
-- The raw file joins two NBA feeds with different shapes, and this model maps both
-- onto one set of columns (feed_format says which a row came from):
--   legacy (1996-97 to early 2019-20, periodType null): Title Case action types
--     ("Made Shot"); scores only on scoring rows (0 elsewhere); assists and the
--     player coming in on a substitution exist only as names in the description;
--     no steal, block or possession data.
--   live (2019-20 onward): lower-case action types ("2pt"); score on every row;
--     assist, steal, block and foul-drawn person ids; substitutions as separate
--     in/out rows.
-- Materialised as a table, not a view: 18.8M rows with a per-game window to carry
-- the score forward, read by every play-by-play mart.
{{ config(materialized='table') }}

WITH source AS (
    SELECT *
    FROM
        {{ source('raw_nba', 'raw_nba_play_by_play') }}
),

-- Transform
cleaned AS (
    SELECT
        *,
        gameId::BIGINT AS game_id_int,
        CASE WHEN periodType IS NULL THEN 'legacy' ELSE 'live' END AS feed_format,
        LOWER(REPLACE(TRIM(actionType), ' ', '')) AS action_key,
        TRIM(REPLACE(shotResult, ':', '')) AS shot_result_clean,
        -- Clock is ISO 8601 (PT11M56.00S): time left in the period.
        REGEXP_EXTRACT(clock, 'PT(\d+)M', 1)::INTEGER * 60
        + REGEXP_EXTRACT(clock, 'M([\d.]+)S', 1)::DOUBLE AS clock_seconds_remaining
    FROM
        source
),

typed AS (
    SELECT
        *,
        CASE
            WHEN action_key IN ('madeshot', 'missedshot', '2pt', '3pt') THEN 'field_goal'
            WHEN action_key = 'freethrow' THEN 'free_throw'
            WHEN action_key = 'jumpball' THEN 'jump_ball'
            WHEN action_key = 'instantreplay' THEN 'instant_replay'
            WHEN action_key = '' THEN 'unknown'
            ELSE action_key
        END AS event_type
    FROM
        cleaned
),

shots AS (
    SELECT
        *,
        CASE
            WHEN event_type = 'field_goal' AND feed_format = 'legacy' THEN action_key = 'madeshot'
            WHEN event_type = 'free_throw' AND feed_format = 'legacy' THEN description NOT ILIKE 'MISS%'
            WHEN event_type IN ('field_goal', 'free_throw') THEN shot_result_clean = 'Made'
        END AS is_shot_made,
        CASE
            WHEN event_type = 'free_throw' THEN 1
            WHEN event_type = 'field_goal' AND feed_format = 'legacy' THEN shotValue
            WHEN action_key = '3pt' THEN 3
            WHEN action_key = '2pt' THEN 2
        END AS shot_value
    FROM
        typed
)

SELECT
    game_id_int AS game_id,
    actionNumber AS action_number,
    ROW_NUMBER() OVER game_sequence AS event_order,
    {{ nba_game_type('game_id_int') }} AS game_type,
    {{ nba_season_start_year('game_id_int') }} AS season_start_year,
    TRY_CAST(gameDateTimeEst AS TIMESTAMP) AS game_datetime_est,
    feed_format,
    period,
    period > 4 AS is_overtime,
    clock_seconds_remaining,
    -- Regulation periods are 12 minutes, overtimes 5.
    CASE
        WHEN period <= 4 THEN (period - 1) * 720 + (720 - clock_seconds_remaining)
        ELSE 2880 + (period - 5) * 300 + (300 - clock_seconds_remaining)
    END AS game_seconds_elapsed,
    event_type,
    NULLIF(TRIM(subType), '') AS event_sub_type,
    NULLIF(TRIM(descriptor), '') AS event_descriptor,
    description,
    -- personId is 0 for game events and a team id (1610612xxx) for team events.
    CASE
        WHEN TRY_CAST(personId AS BIGINT) BETWEEN 1610612000 AND 1610612999 THEN NULL
        ELSE NULLIF(TRY_CAST(personId AS BIGINT), 0)
    END AS person_id,
    COALESCE(playerFullName, playerNameI, playerName) AS feed_player_name,
    TRY_CAST(teamId AS BIGINT) AS team_id,
    teamTricode AS team_tricode,
    -- Legacy rows only carry the score on scoring plays, so carry the last score forward.
    COALESCE(
        LAST_VALUE(
            CASE WHEN feed_format = 'live' OR scoreHome + scoreAway > 0 THEN scoreHome END IGNORE NULLS
        ) OVER game_order,
        0
    ) AS score_home,
    COALESCE(
        LAST_VALUE(
            CASE WHEN feed_format = 'live' OR scoreHome + scoreAway > 0 THEN scoreAway END IGNORE NULLS
        ) OVER game_order,
        0
    ) AS score_away,
    is_shot_made,
    shot_value,
    CASE WHEN is_shot_made THEN shot_value ELSE 0 END AS points_scored,
    -- Court coordinates in tenths of a foot from the basket, set for every field goal but
    -- a handful. The legacy feed puts shots at the rim at exactly 0,0.
    CASE WHEN event_type = 'field_goal' THEN xLegacy END AS shot_x,
    CASE WHEN event_type = 'field_goal' THEN yLegacy END AS shot_y,
    -- Distance from the coordinates: the legacy feed's own distance is parsed from the
    -- description and is 0 whenever the text gives none (many threes, some jumpers).
    CASE
        WHEN event_type = 'field_goal'
            THEN COALESCE(ROUND(SQRT(xLegacy * xLegacy + yLegacy * yLegacy) / 10, 1), shotDistance)
    END AS shot_distance_ft,
    CASE WHEN event_type = 'field_goal' THEN area END AS shot_area,
    CASE WHEN event_type = 'field_goal' THEN areaDetail END AS shot_area_detail,
    CASE WHEN feed_format = 'live' THEN qualifiers END AS qualifiers,
    assistPersonId::BIGINT AS assist_person_id,
    -- Legacy assists are text: "(Korver 1 AST)".
    CASE
        WHEN feed_format = 'legacy' AND event_type = 'field_goal'
            THEN NULLIF(REGEXP_EXTRACT(description, '\(([^()]+) \d+ AST\)', 1), '')
    END AS legacy_assist_name,
    stealPersonId::BIGINT AS steal_person_id,
    blockPersonId::BIGINT AS block_person_id,
    foulDrawnPersonId::BIGINT AS foul_drawn_person_id,
    -- Legacy substitutions are one row, "SUB: <in> FOR <out>", with person_id the player going out.
    CASE
        WHEN feed_format = 'legacy' AND event_type = 'substitution'
            THEN NULLIF(REGEXP_EXTRACT(description, '^SUB: (.+) FOR ', 1), '')
    END AS legacy_sub_in_name,
    CASE WHEN feed_format = 'live' THEN NULLIF(TRY_CAST(possession AS BIGINT), 0) END AS possession_team_id,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    shots
-- Game order is game time: period, then clock counting down. actionNumber alone is not:
-- it is the id an event was created with, so live-feed edits and inserts get later
-- numbers (orderNumber is the live feed's own sequence), and legacy reviews were often
-- logged after the period ended. Ties keep the feed's order.
WINDOW
    game_sequence AS (
        PARTITION BY game_id_int
        ORDER BY period ASC, clock_seconds_remaining DESC, COALESCE(orderNumber, actionNumber) ASC, actionNumber ASC
    ),
    game_order AS (game_sequence ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
