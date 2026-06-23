-- One row per game combining game metadata with both teams' box score lines.
-- Team box scores are pivoted onto the home/away axis via conditional aggregation.
with games as (
    select * from {{ ref('stg_nba_games') }}
),

team_box as (
    select * from {{ ref('stg_nba_team_statistics') }}
),

game_team_stats as (
    select
        game_id,
        max(case when is_home then field_goals_made          end)    as home_field_goals_made,
        max(case when is_home then field_goals_attempted     end)    as home_field_goals_attempted,
        max(case when is_home then three_pointers_made        end)    as home_three_pointers_made,
        max(case when is_home then rebounds_total             end)    as home_rebounds_total,
        max(case when is_home then assists                    end)    as home_assists,
        max(case when is_home then turnovers                  end)    as home_turnovers,
        max(case when is_home then points_in_the_paint        end)    as home_points_in_the_paint,
        max(case when not is_home then field_goals_made       end)    as away_field_goals_made,
        max(case when not is_home then field_goals_attempted  end)    as away_field_goals_attempted,
        max(case when not is_home then three_pointers_made    end)    as away_three_pointers_made,
        max(case when not is_home then rebounds_total         end)    as away_rebounds_total,
        max(case when not is_home then assists                end)    as away_assists,
        max(case when not is_home then turnovers              end)    as away_turnovers,
        max(case when not is_home then points_in_the_paint    end)    as away_points_in_the_paint
    from team_box
    group by game_id
)

select
    g.game_id,
    g.game_date,
    g.game_datetime_est,
    g.game_type,
    g.home_team_id,
    g.home_team_name,
    g.away_team_id,
    g.away_team_name,
    g.home_score,
    g.away_score,
    g.home_score - g.away_score         as point_margin,
    g.home_team_won,
    g.attendance,
    g.arena_name,
    s.home_field_goals_made,
    s.home_field_goals_attempted,
    s.home_three_pointers_made,
    s.home_rebounds_total,
    s.home_assists,
    s.home_turnovers,
    s.home_points_in_the_paint,
    s.away_field_goals_made,
    s.away_field_goals_attempted,
    s.away_three_pointers_made,
    s.away_rebounds_total,
    s.away_assists,
    s.away_turnovers,
    s.away_points_in_the_paint,
    g.ingested_at
from games g
left join game_team_stats s using (game_id)
order by g.game_date desc
