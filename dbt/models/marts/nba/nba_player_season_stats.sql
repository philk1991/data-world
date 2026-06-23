-- One row per player per season per game type (Regular Season, Playoffs, etc.)
-- of traditional box score totals, per-game averages and shooting splits,
-- enriched with bio. Season is derived from the game date (months before July
-- belong to the prior start year). A player traded mid-season is combined into a
-- single row per game type; primary_team_id is the team they played the most
-- games for. Only games actually played (minutes_played not null) count.
with box_scores as (
    select * from {{ ref('stg_nba_player_statistics') }}
),

players as (
    select * from {{ ref('stg_nba_players') }}
),

seasoned as (
    select
        person_id,
        case
            when month(game_date) >= 7 then year(game_date)
            else year(game_date) - 1
        end                                                         as season_start_year,
        game_type,
        player_team_id,
        game_id,
        points,
        rebounds_total,
        assists,
        steals,
        blocks,
        turnovers,
        field_goals_made,
        field_goals_attempted,
        three_pointers_made,
        three_pointers_attempted,
        free_throws_made,
        free_throws_attempted
    from box_scores
    where person_id is not null
        and minutes_played is not null
        and game_date is not null
        and game_type is not null
),

season_totals as (
    select
        person_id,
        season_start_year,
        game_type,
        mode(player_team_id)                                        as primary_team_id,
        count(distinct game_id)                                     as games_played,
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
    from seasoned
    group by person_id, season_start_year, game_type
)

select
    s.person_id,
    p.first_name,
    p.last_name,
    s.season_start_year,
    s.season_start_year::varchar || '-'
        || right((s.season_start_year + 1)::varchar, 2)            as season_label,
    s.game_type,
    s.primary_team_id,
    s.games_played,
    s.total_points,
    s.total_rebounds,
    s.total_assists,
    s.total_steals,
    s.total_blocks,
    s.total_turnovers,
    round(s.total_points::double  / nullif(s.games_played, 0), 1)  as points_per_game,
    round(s.total_rebounds::double / nullif(s.games_played, 0), 1) as rebounds_per_game,
    round(s.total_assists::double / nullif(s.games_played, 0), 1)  as assists_per_game,
    round(s.total_field_goals_made::double
          / nullif(s.total_field_goals_attempted, 0), 3)           as field_goal_pct,
    round(s.total_three_pointers_made::double
          / nullif(s.total_three_pointers_attempted, 0), 3)        as three_point_pct,
    round(s.total_free_throws_made::double
          / nullif(s.total_free_throws_attempted, 0), 3)           as free_throw_pct
from season_totals s
left join players p using (person_id)
order by s.season_start_year desc, s.total_points desc
