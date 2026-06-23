-- All-time matchup record, one row per ordered (team_id, opponent_team_id) pair.
-- Each game contributes one team-perspective row in the source, so a team's row
-- against an opponent is its record directly; the reverse matchup is a separate
-- row. Restricted to competitive meetings (Regular Season + Playoffs) to exclude
-- preseason and exhibition games. Join nba_team_dim on either id for team names.
with team_box as (
    select * from {{ ref('stg_nba_team_statistics') }}
),

matchups as (
    select
        team_id,
        opponent_team_id,
        game_id,
        game_date,
        is_win,
        team_score,
        opponent_score
    from team_box
    where game_type in ('Regular Season', 'Playoffs')
        and opponent_team_id is not null
)

select
    team_id,
    opponent_team_id,
    count(distinct game_id)                                         as games_played,
    count(case when is_win then 1 end)                             as wins,
    count(case when is_win = false then 1 end)                     as losses,
    round(count(case when is_win then 1 end)::double
          / nullif(count(case when is_win is not null then 1 end), 0), 3) as win_pct,
    round(avg(team_score), 1)                                      as avg_points_for,
    round(avg(opponent_score), 1)                                  as avg_points_against,
    round(avg(team_score - opponent_score), 1)                    as avg_point_margin,
    min(game_date)                                                 as first_meeting_date,
    max(game_date)                                                 as last_meeting_date
from matchups
group by team_id, opponent_team_id
order by games_played desc
