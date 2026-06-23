-- One row per player aggregating their traditional box score totals and
-- averages across every game they appeared in, enriched with player bio.
-- Only games the player actually played (minutes_played is not null) count.
with box_scores as (
    select * from {{ ref('stg_nba_player_statistics') }}
),

players as (
    select * from {{ ref('stg_nba_players') }}
),

career as (
    select
        person_id,
        count(distinct game_id)                                     as games_played,
        min(game_date)                                              as first_game_date,
        max(game_date)                                              as last_game_date,
        sum(points)                                                 as total_points,
        sum(rebounds_total)                                         as total_rebounds,
        sum(assists)                                                as total_assists,
        sum(steals)                                                 as total_steals,
        sum(blocks)                                                 as total_blocks,
        sum(turnovers)                                              as total_turnovers,
        sum(field_goals_made)                                       as total_field_goals_made,
        sum(field_goals_attempted)                                  as total_field_goals_attempted,
        sum(three_pointers_made)                                    as total_three_pointers_made,
        sum(three_pointers_attempted)                               as total_three_pointers_attempted,
        sum(free_throws_made)                                       as total_free_throws_made,
        sum(free_throws_attempted)                                  as total_free_throws_attempted
    from box_scores
    where person_id is not null
        and minutes_played is not null
    group by person_id
),

career_rates as (
    select
        person_id,
        games_played,
        first_game_date,
        last_game_date,
        total_points,
        total_rebounds,
        total_assists,
        total_steals,
        total_blocks,
        total_turnovers,
        round(total_points::double  / nullif(games_played, 0), 1)   as points_per_game,
        round(total_rebounds::double / nullif(games_played, 0), 1)  as rebounds_per_game,
        round(total_assists::double / nullif(games_played, 0), 1)   as assists_per_game,
        round(total_field_goals_made::double
              / nullif(total_field_goals_attempted, 0), 3)          as career_field_goal_pct,
        round(total_three_pointers_made::double
              / nullif(total_three_pointers_attempted, 0), 3)       as career_three_point_pct,
        round(total_free_throws_made::double
              / nullif(total_free_throws_attempted, 0), 3)          as career_free_throw_pct
    from career
)

select
    c.person_id,
    p.first_name,
    p.last_name,
    p.is_guard,
    p.is_forward,
    p.is_center,
    p.draft_year,
    p.height_inches,
    c.first_game_date,
    c.last_game_date,
    c.games_played,
    c.total_points,
    c.total_rebounds,
    c.total_assists,
    c.total_steals,
    c.total_blocks,
    c.total_turnovers,
    c.points_per_game,
    c.rebounds_per_game,
    c.assists_per_game,
    c.career_field_goal_pct,
    c.career_three_point_pct,
    c.career_free_throw_pct
from career_rates c
left join players p using (person_id)
order by c.total_points desc
