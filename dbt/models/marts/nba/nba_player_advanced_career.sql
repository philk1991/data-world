-- One row per player summarising advanced career efficiency, enriched with bio.
-- Sourced from the advanced player box scores (available since ~1996), so the
-- careers of earlier players are not represented. Rate metrics are minutes-weighted
-- (sum(metric * minutes) / sum(minutes)) so high-minute games count for more than
-- garbage-time cameos; only games with recorded minutes and advanced data count.
with player_advanced as (
    select * from {{ ref('stg_nba_player_statistics_extended') }}
),

players as (
    select * from {{ ref('stg_nba_players') }}
),

weighted as (
    select
        person_id,
        count(distinct game_id)                                     as games_with_advanced,
        sum(minutes_played)                                         as total_minutes,
        count(case when is_double_double then 1 end)               as double_doubles,
        count(case when is_triple_double then 1 end)               as triple_doubles,
        sum(usage_percentage * minutes_played)                     as w_usage,
        sum(true_shooting_percentage * minutes_played)             as w_true_shooting,
        sum(effective_field_goal_percentage * minutes_played)     as w_efg,
        sum(offensive_rating * minutes_played)                     as w_offensive_rating,
        sum(defensive_rating * minutes_played)                     as w_defensive_rating,
        sum(net_rating * minutes_played)                          as w_net_rating,
        sum(assist_percentage * minutes_played)                   as w_assist,
        sum(rebound_percentage * minutes_played)                  as w_rebound,
        sum(player_impact_estimate * minutes_played)             as w_pie
    from player_advanced
    where person_id is not null
        and minutes_played is not null
        and minutes_played > 0
        and offensive_rating is not null
    group by person_id
)

select
    w.person_id,
    p.first_name,
    p.last_name,
    p.is_guard,
    p.is_forward,
    p.is_center,
    w.games_with_advanced,
    round(w.total_minutes / nullif(w.games_with_advanced, 0), 1)   as minutes_per_game,
    w.double_doubles,
    w.triple_doubles,
    round(w.w_usage / nullif(w.total_minutes, 0), 3)              as usage_pct,
    round(w.w_true_shooting / nullif(w.total_minutes, 0), 3)      as true_shooting_pct,
    round(w.w_efg / nullif(w.total_minutes, 0), 3)               as effective_field_goal_pct,
    round(w.w_offensive_rating / nullif(w.total_minutes, 0), 1)  as offensive_rating,
    round(w.w_defensive_rating / nullif(w.total_minutes, 0), 1)  as defensive_rating,
    round(w.w_net_rating / nullif(w.total_minutes, 0), 1)        as net_rating,
    round(w.w_assist / nullif(w.total_minutes, 0), 3)            as assist_pct,
    round(w.w_rebound / nullif(w.total_minutes, 0), 3)           as rebound_pct,
    round(w.w_pie / nullif(w.total_minutes, 0), 3)              as player_impact_estimate
from weighted w
left join players p using (person_id)
order by w.triple_doubles desc, net_rating desc
