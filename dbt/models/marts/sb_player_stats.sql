-- Aggregated player statistics across all StatsBomb open data matches.
-- One row per (player_id, team) — a player who transferred between clubs will
-- appear as multiple rows, one per team they played for in the dataset.
--
-- Note: shot_outcome (goals, assists) is not extracted into raw_sb_events at
-- this stage. total_shots is a count of Shot events; goals require a future
-- extension to add shot_outcome to the raw table.
with events as (
    select * from {{ ref('stg_sb_events') }}
),

lineups as (
    select * from {{ ref('stg_sb_lineups') }}
),

player_events as (
    select
        player_id,
        player_name,
        team,
        count(distinct match_id)                                    as matches_in_events,
        count(*)                                                    as total_events,
        count(case when event_type = 'Pass'     then 1 end)        as total_passes,
        count(case when event_type = 'Shot'     then 1 end)        as total_shots,
        count(case when event_type = 'Dribble'  then 1 end)        as total_dribbles,
        count(case when event_type = 'Pressure' then 1 end)        as total_pressures,
        count(case when event_type = 'Carry'    then 1 end)        as total_carries,
        round(sum(coalesce(duration, 0)) / 60.0, 2)                as total_duration_minutes
    from events
    where player_id is not null
    group by player_id, player_name, team
),

player_appearances as (
    select
        player_id,
        team_name                                                   as team,
        count(distinct match_id)                                    as lineup_appearances,
        max(country_name)                                           as country_name
    from lineups
    group by player_id, team_name
)

select
    pe.player_id,
    pe.player_name,
    pe.team,
    pa.country_name,
    coalesce(pa.lineup_appearances, 0)  as lineup_appearances,
    pe.matches_in_events,
    pe.total_events,
    pe.total_passes,
    pe.total_shots,
    pe.total_dribbles,
    pe.total_pressures,
    pe.total_carries,
    pe.total_duration_minutes
from player_events pe
left join player_appearances pa
    on pe.player_id = pa.player_id
    and pe.team = pa.team
order by pe.total_shots desc
