-- Staged StatsBomb events.
-- Casts types and derives seconds_elapsed from minute and second.
-- location_x and location_y are already parsed to DOUBLE in raw.
WITH source AS (
    SELECT *
    FROM
        {{ source('raw_statsbomb', 'raw_sb_events') }}
)

SELECT
    event_id,
    match_id,
    event_index,
    period,
    timestamp::TIME AS event_time,
    minute,
    second,
    (minute * 60) + second AS seconds_elapsed,
    event_type,
    possession,
    possession_team,
    play_pattern,
    team,
    player_id,
    player_name,
    location_x,
    location_y,
    duration,
    ingested_at::TIMESTAMP AS ingested_at
FROM
    source
