-- One row per team per regular season summarising advanced efficiency metrics.
-- Sourced from the advanced team box scores (available since ~1996), so earlier
-- seasons are absent. Season is derived from the game date the same way as
-- nba_team_season_summary. Each regular-season game is a near-uniform number of
-- possessions, so per-game ratings are summarised with a simple mean.
with team_advanced as (
    select * from {{ ref('stg_nba_team_statistics_extended') }}
),

seasoned as (
    select
        team_id,
        case
            when month(game_datetime_est) >= 7 then year(game_datetime_est)
            else year(game_datetime_est) - 1
        end                                                         as season_start_year,
        offensive_rating,
        defensive_rating,
        net_rating,
        pace,
        effective_field_goal_percentage,
        true_shooting_percentage,
        assist_percentage,
        rebound_percentage,
        team_turnover_percentage,
        percent_field_goal_attempts_3_point,
        percent_points_in_paint,
        percent_points_fast_break
    from team_advanced
    where game_type = 'Regular Season'
)

select
    team_id,
    season_start_year,
    season_start_year::varchar || '-'
        || right((season_start_year + 1)::varchar, 2)              as season_label,
    count(*)                                                        as games_played,
    round(avg(offensive_rating), 1)                                as offensive_rating,
    round(avg(defensive_rating), 1)                                as defensive_rating,
    round(avg(net_rating), 1)                                      as net_rating,
    round(avg(pace), 1)                                            as pace,
    round(avg(effective_field_goal_percentage), 3)                as effective_field_goal_pct,
    round(avg(true_shooting_percentage), 3)                       as true_shooting_pct,
    round(avg(assist_percentage), 3)                              as assist_pct,
    round(avg(rebound_percentage), 3)                             as rebound_pct,
    round(avg(team_turnover_percentage), 3)                       as turnover_pct,
    round(avg(percent_field_goal_attempts_3_point), 3)           as three_point_attempt_rate,
    round(avg(percent_points_in_paint), 3)                        as points_in_paint_share,
    round(avg(percent_points_fast_break), 3)                      as fast_break_points_share
from seasoned
group by team_id, season_start_year
order by season_start_year desc, net_rating desc
