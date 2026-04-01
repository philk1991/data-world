-- One row per match with competition context and aggregate event counts.
-- Event counts use conditional aggregation over the event type column.
with matches as (
    select * from {{ ref('stg_sb_matches') }}
),

event_counts as (
    select
        match_id,
        count(*)                                                    as total_events,
        count(case when event_type = 'Shot'     then 1 end)        as total_shots,
        count(case when event_type = 'Pass'     then 1 end)        as total_passes,
        count(case when event_type = 'Dribble'  then 1 end)        as total_dribbles,
        count(case when event_type = 'Pressure' then 1 end)        as total_pressures,
        count(case when event_type = 'Carry'    then 1 end)        as total_carries
    from {{ ref('stg_sb_events') }}
    group by match_id
)

select
    m.match_id,
    m.match_date,
    m.competition_id,
    m.competition_name,
    m.season_id,
    m.season_name,
    m.home_team_name,
    m.away_team_name,
    m.home_score,
    m.away_score,
    m.goal_difference,
    m.match_result,
    m.match_week,
    m.competition_stage,
    m.stadium_name,
    coalesce(e.total_events,    0)      as total_events,
    coalesce(e.total_shots,     0)      as total_shots,
    coalesce(e.total_passes,    0)      as total_passes,
    coalesce(e.total_dribbles,  0)      as total_dribbles,
    coalesce(e.total_pressures, 0)      as total_pressures,
    coalesce(e.total_carries,   0)      as total_carries,
    m.ingested_at
from matches m
left join event_counts e using (match_id)
order by m.match_date desc
