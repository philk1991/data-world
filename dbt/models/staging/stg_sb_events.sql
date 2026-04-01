-- Staged StatsBomb events.
-- Casts types and derives seconds_elapsed from minute and second.
-- location_x and location_y are already parsed to DOUBLE in raw.
with source as (
    select * from {{ source('raw', 'raw_sb_events') }}
)

select
    event_id,
    match_id,
    event_index,
    period,
    timestamp::time                     as event_time,
    minute,
    second,
    (minute * 60) + second              as seconds_elapsed,
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
    ingested_at::timestamp              as ingested_at
from source
