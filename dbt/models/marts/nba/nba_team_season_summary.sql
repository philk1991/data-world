-- One row per team per regular season with their win/loss record and scoring
-- averages. The NBA season spans two calendar years (Oct-Apr), so the season is
-- derived from the game date: months before July belong to the prior start year.
-- Restricted to Regular Season games so the record reflects the standings.
with team_box as (
    select * from {{ ref('stg_nba_team_statistics') }}
),

seasoned as (
    select
        team_id,
        case
            when month(game_date) >= 7 then year(game_date)
            else year(game_date) - 1
        end                                                         as season_start_year,
        is_win,
        is_home,
        team_score,
        opponent_score
    from team_box
    where game_type = 'Regular Season'
),

team_season as (
    select
        team_id,
        season_start_year,
        count(*)                                                    as games_played,
        count(case when is_win then 1 end)                          as wins,
        count(case when is_win = false then 1 end)                  as losses,
        count(case when is_home and is_win then 1 end)              as home_wins,
        count(case when not is_home and is_win then 1 end)          as away_wins,
        sum(team_score)                                             as total_points_for,
        sum(opponent_score)                                         as total_points_against
    from seasoned
    group by team_id, season_start_year
)

select
    team_id,
    season_start_year,
    season_start_year::varchar || '-'
        || right((season_start_year + 1)::varchar, 2)              as season_label,
    games_played,
    wins,
    losses,
    home_wins,
    away_wins,
    round(wins::double / nullif(wins + losses, 0), 3)              as win_pct,
    round(total_points_for::double / nullif(games_played, 0), 1)  as points_for_per_game,
    round(total_points_against::double
          / nullif(games_played, 0), 1)                           as points_against_per_game,
    round((total_points_for - total_points_against)::double
          / nullif(games_played, 0), 1)                           as point_margin_per_game
from team_season
order by season_start_year desc, win_pct desc
