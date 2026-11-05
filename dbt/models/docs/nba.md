{#
    Column descriptions shared across the NBA staging and mart models.

    A column that appears in more than one NBA model takes its description from
    a block here, so the wording cannot drift between models; model-specific
    context follows the doc() call in the YAML. Where two models share a column
    name but not its meaning, the blocks are named variants:
    nba__<column>__<variant>. `task dbt:docs:check` enforces both rules.
#}

{# ── Games ─────────────────────────────────────────────────────────────── #}

{% docs nba__game_id %}
NBA game identifier. Encodes the game type and season (00TYYNNNNN, stored without the leading zeros); game_type and season_start_year are decoded from it.
{% enddocs %}

{% docs nba__game_type %}
Type of game, decoded from the game id: Regular Season, Playoffs, Play-in Tournament, Preseason, All-Star Game or NBA Cup Final. NBA Cup group and knockout games are Regular Season; only the Cup final, which does not count toward the standings, is separate.
{% enddocs %}

{% docs nba__season_start_year %}
Calendar year the season started (e.g. 2023 for 2023-24), decoded from the game id. Follows the league's own season assignment, so the 2020 bubble games belong to 2019-20 and the July 2021 Finals to 2020-21.
{% enddocs %}

{% docs nba__season_label %}
Human-readable season label (e.g. "2023-24").
{% enddocs %}

{% docs nba__game_date %}
Calendar date of the game.
{% enddocs %}

{% docs nba__game_datetime_est %}
Scheduled tip-off timestamp (US Eastern).
{% enddocs %}

{% docs nba__home_team_id %}
Franchise identifier of the home side.
{% enddocs %}

{% docs nba__away_team_id %}
Franchise identifier of the away side.
{% enddocs %}

{% docs nba__home_score %}
Final points scored by the home team.
{% enddocs %}

{% docs nba__away_score %}
Final points scored by the away team.
{% enddocs %}

{% docs nba__home_team_won %}
True when the home team won.
{% enddocs %}

{% docs nba__attendance %}
Reported attendance. Only populated from 2025-26; null for every earlier game in the upstream data.
{% enddocs %}

{% docs nba__ingested_at %}
When the source row was ingested.
{% enddocs %}

{# ── Teams ─────────────────────────────────────────────────────────────── #}

{% docs nba__team_id %}
Franchise identifier, stable across relocations and renames.
{% enddocs %}

{% docs nba__opponent_team_id %}
Franchise identifier of the opposing team.
{% enddocs %}

{% docs nba__is_home %}
True when the team in this row (for a player, their team) was the home side.
{% enddocs %}

{% docs nba__is_win %}
True when the team in this row (for a player, their team) won. Null when the result is unknown.
{% enddocs %}

{% docs nba__wins %}
Games won by team_id.
{% enddocs %}

{% docs nba__losses %}
Games lost by team_id.
{% enddocs %}

{% docs nba__win_pct %}
Wins divided by decided games (wins + losses), 0-1.
{% enddocs %}

{% docs nba__games_played__team %}
Regular season games the team played that season.
{% enddocs %}

{% docs nba__games_played__team_advanced %}
Games the team played that season in this game type.
{% enddocs %}

{% docs nba__games_played__head_to_head %}
Competitive meetings (Regular Season and Playoffs) between the two teams.
{% enddocs %}

{# ── Players ───────────────────────────────────────────────────────────── #}

{% docs nba__person_id %}
NBA player identifier.
{% enddocs %}

{% docs nba__player_team_id %}
Team the player played for. Null for many older games, where team ids were not recorded.
{% enddocs %}

{% docs nba__first_name %}
Player first name. Missing for a couple of historical players.
{% enddocs %}

{% docs nba__last_name %}
Player last name. Missing for a couple of historical players.
{% enddocs %}

{% docs nba__draft_year %}
Year the player was drafted; null if undrafted or unknown.
{% enddocs %}

{% docs nba__draft_round %}
Round the player was drafted in; null if undrafted or unknown.
{% enddocs %}

{% docs nba__draft_number %}
Overall pick number the player was drafted with; null if undrafted or unknown.
{% enddocs %}

{% docs nba__is_undrafted %}
True when the player went undrafted, false when drafted, null when draft status is unknown.
{% enddocs %}

{% docs nba__birth_date %}
Date of birth; null when unknown or when the source carries a placeholder date (1900-01-01, 1995-01-01, April 1905).
{% enddocs %}

{% docs nba__height_inches %}
Listed height in inches; null when unknown.
{% enddocs %}

{% docs nba__body_weight_lbs %}
Listed weight in pounds; null when unknown. A single current listing, not a per-season weight.
{% enddocs %}

{% docs nba__is_guard %}
True when the player is listed as a guard.
{% enddocs %}

{% docs nba__is_forward %}
True when the player is listed as a forward.
{% enddocs %}

{% docs nba__is_center %}
True when the player is listed as a center.
{% enddocs %}

{% docs nba__first_game_date %}
Date of the player's earliest competitive game (Regular Season, Playoffs, Play-in Tournament or NBA Cup Final) with recorded minutes in the dataset. Null for a handful of historical players whose box score rows carry no game date.
{% enddocs %}

{% docs nba__last_game_date %}
Date of the player's most recent competitive game (Regular Season, Playoffs, Play-in Tournament or NBA Cup Final) with recorded minutes in the dataset. Null for a handful of historical players whose box score rows carry no game date.
{% enddocs %}

{% docs nba__games_played__player %}
Distinct games the player appeared in with recorded minutes.
{% enddocs %}

{# ── Player totals and per-game rates (grain comes from the model) ─────── #}

{% docs nba__total_points %}
Total points scored.
{% enddocs %}

{% docs nba__total_rebounds %}
Total rebounds.
{% enddocs %}

{% docs nba__total_assists %}
Total assists.
{% enddocs %}

{% docs nba__total_steals %}
Total steals. Null when none of the games had steals recorded (the league started tracking them in 1973-74).
{% enddocs %}

{% docs nba__total_blocks %}
Total blocks. Null when none of the games had blocks recorded (the league started tracking them in 1973-74).
{% enddocs %}

{% docs nba__total_turnovers %}
Total turnovers. Null when none of the games had turnovers recorded (player turnovers start in 1977-78).
{% enddocs %}

{% docs nba__points_per_game %}
Points per game played.
{% enddocs %}

{% docs nba__rebounds_per_game %}
Rebounds per game played.
{% enddocs %}

{% docs nba__assists_per_game %}
Assists per game played.
{% enddocs %}

{# ── Per-game box score values and shooting splits ─────────────────────── #}

{% docs nba__minutes_played %}
Minutes played in the game.
{% enddocs %}

{% docs nba__points %}
Points scored in the game.
{% enddocs %}

{% docs nba__field_goals_made %}
Field goals made.
{% enddocs %}

{% docs nba__field_goals_attempted %}
Field goals attempted.
{% enddocs %}

{% docs nba__three_pointers_made %}
Three pointers made.
{% enddocs %}

{% docs nba__three_pointers_attempted %}
Three pointers attempted.
{% enddocs %}

{% docs nba__free_throws_made %}
Free throws made.
{% enddocs %}

{% docs nba__free_throws_attempted %}
Free throws attempted.
{% enddocs %}

{% docs nba__rebounds_offensive %}
Offensive rebounds; null before rebounds were split (1973-74).
{% enddocs %}

{% docs nba__rebounds_defensive %}
Defensive rebounds; null before rebounds were split (1973-74).
{% enddocs %}

{% docs nba__rebounds_total %}
Total rebounds.
{% enddocs %}

{% docs nba__assists %}
Assists.
{% enddocs %}

{% docs nba__steals %}
Steals; null before the league tracked them (1973-74).
{% enddocs %}

{% docs nba__blocks %}
Blocks; null before the league tracked them (1973-74).
{% enddocs %}

{% docs nba__turnovers %}
Turnovers; null where they were not recorded (player turnovers start in 1977-78).
{% enddocs %}

{% docs nba__fouls_personal %}
Personal fouls.
{% enddocs %}

{% docs nba__field_goal_pct %}
Field goal percentage (made / attempted), 0-1.
{% enddocs %}

{% docs nba__three_point_pct %}
Three point percentage (made / attempted), 0-1.
{% enddocs %}

{% docs nba__free_throw_pct %}
Free throw percentage (made / attempted), 0-1.
{% enddocs %}

{# ── Advanced metrics (box scores from 1996-97) ────────────────────────── #}

{% docs nba__offensive_rating %}
Points per 100 possessions: scored, for a team, or produced while on the floor, for a player.
{% enddocs %}

{% docs nba__defensive_rating %}
Points allowed per 100 possessions (for a player, while on the floor).
{% enddocs %}

{% docs nba__net_rating %}
Offensive rating minus defensive rating.
{% enddocs %}

{% docs nba__pace %}
Estimated possessions per 48 minutes.
{% enddocs %}

{% docs nba__player_impact_estimate %}
PIE: the player's share of the game's total statistical contribution.
{% enddocs %}

{% docs nba__true_shooting_pct %}
True shooting percentage, PTS / (2 × (FGA + 0.44 × FTA)): shooting efficiency counting twos, threes and free throws.
{% enddocs %}

{% docs nba__effective_field_goal_pct %}
Effective field goal percentage, (FGM + 0.5 × 3PM) / FGA: field goal percentage adjusted for the extra value of a three.
{% enddocs %}

{% docs nba__rebound_pct %}
Share of available rebounds secured (for a player, while on the floor), 0-1.
{% enddocs %}

{% docs nba__assist_pct__player %}
Share of teammates' made field goals the player assisted while on the floor, 0-1.
{% enddocs %}

{% docs nba__usage_pct %}
Usage rate: share of the team's plays the player used while on the floor, 0-1.
{% enddocs %}

{% docs nba__assist_pct__team %}
Share of the team's made field goals that were assisted, 0-1.
{% enddocs %}

{# ── Team metrics (macros/nba_metrics.sql; box-estimated from 1973-74) ──── #}

{% docs nba__point_margin__game %}
Home score minus away score. Positive means the home team won.
{% enddocs %}

{% docs nba__point_margin__team %}
Points minus opponent points. Positive means the team won.
{% enddocs %}

{% docs nba__possessions %}
Box-estimated possessions, Basketball-Reference's formula: the mean of the team's and the opponent's FGA + 0.4 × FTA − 1.07 × ORB% × (FGA − FG) + TOV. Null before 1973-74 and where an input is missing. Not the play-by-play possession count.
{% enddocs %}

{% docs nba__team_minutes %}
Team player-minutes: 240 for a regulation game plus 25 per overtime. Where the team box records 0, rounded from the players' summed minutes; null when neither was recorded (most games before 1964-65).
{% enddocs %}

{% docs nba__opp_points %}
Points the opponent scored.
{% enddocs %}

{% docs nba__turnover_pct %}
Turnovers per play, TOV / (FGA + 0.44 × FTA + TOV), 0-1 (a Four Factor).
{% enddocs %}

{% docs nba__offensive_rebound_pct %}
Share of available offensive rebounds secured, 0-1: ORB / (ORB + opponent DRB) for a team (a Four Factor); for a player, of those available while on the floor.
{% enddocs %}

{% docs nba__defensive_rebound_pct %}
Share of available defensive rebounds secured, 0-1: DRB / (DRB + opponent ORB) for a team (a defensive Four Factor); for a player, of those available while on the floor.
{% enddocs %}

{% docs nba__free_throw_rate %}
Free throws made per field goal attempt, FT / FGA (a Four Factor).
{% enddocs %}

{% docs nba__opp_effective_field_goal_pct %}
Opponent's effective field goal percentage (a defensive Four Factor), 0-1.
{% enddocs %}

{% docs nba__opp_turnover_pct %}
Opponent's turnovers per play (a defensive Four Factor), 0-1.
{% enddocs %}

{% docs nba__opp_free_throw_rate %}
Opponent's free throws made per field goal attempt (a defensive Four Factor).
{% enddocs %}

{% docs nba__three_point_attempt_rate %}
Share of field goal attempts taken from three, 3PA / FGA, 0-1. Null before the three-point line (1979-80).
{% enddocs %}

{% docs nba__counts_source %}
Where the box counts came from: team_box (the team box score), player_sum (summed from complete player box scores, before 1983-84; leaves out team rebounds and team turnovers) or none (not recorded).
{% enddocs %}

{% docs nba__has_full_box %}
True when both teams recorded FGA, FTA, offensive and defensive rebounds and turnovers and the team's minutes are known, so possessions and pace can be estimated.
{% enddocs %}

{% docs nba__formula_version %}
Version of the metric formulas (dbt var nba_metrics_version; definitions in macros/nba_metrics.sql).
{% enddocs %}

{% docs nba__primary_team_id %}
Team the player played the most games for that season.
{% enddocs %}

{# ── Player metrics (box-score estimates; macros/nba_metrics.sql) ──────── #}

{% docs nba__total_minutes %}
Total minutes played. Player minutes are whole minutes (truncated) before 2024-25 and not recorded before 1964-65.
{% enddocs %}

{% docs nba__true_shooting_points_added %}
Points scored above what league-average true shooting (same season and game type) would produce on the player's attempts: PTS − 2 × league TS% × (FGA + 0.44 × FTA).
{% enddocs %}

{% docs nba__steal_pct %}
Share of opponent possessions ending in the player's steal while they were on the floor, 0-1. From 1973-74.
{% enddocs %}

{% docs nba__block_pct %}
Share of opponent two-point attempts the player blocked while on the floor, 0-1. From 1973-74.
{% enddocs %}

{% docs nba__player_possessions %}
Team possessions (box estimate) while the player was on the floor: the team's possessions × the player's share of the team's minutes. The per-100 denominator. From 1973-74.
{% enddocs %}

{% docs nba__per_100 %}
Per 100 possessions the player was on the floor for (player_possessions). From 1973-74.
{% enddocs %}

{% docs nba__game_score %}
Hollinger's Game Score: PTS + 0.4 FG − 0.7 FGA − 0.4 (FTA − FT) + 0.7 ORB + 0.3 DRB + STL + 0.7 AST + 0.7 BLK − 0.4 PF − TOV. Null where any input was not recorded.
{% enddocs %}

{% docs nba__game_score_per_game %}
Average Game Score over the games where every input was recorded.
{% enddocs %}

{% docs nba__rating_games %}
Games with every input of the individual ratings recorded (both teams' full box and all of the player's counts); the sample the individual ratings use.
{% enddocs %}

{% docs nba__points_produced %}
Dean Oliver's points produced (PProd): points the player created through scoring, assists and offensive rebounds, with shared credit. From 1977-78.
{% enddocs %}

{% docs nba__individual_possessions %}
Dean Oliver's individual total possessions (TotPoss): possessions the player used through scoring possessions, missed shots and free throws, and turnovers. From 1977-78.
{% enddocs %}

{% docs nba__individual_offensive_rating %}
Dean Oliver's individual offensive rating: points produced per 100 individual possessions (100 × PProd / TotPoss), Basketball-Reference's method. From 1977-78. Not the NBA's on-court offensive_rating.
{% enddocs %}

{% docs nba__individual_defensive_rating %}
Dean Oliver's individual defensive rating: points allowed per 100 possessions, the team's defensive rating moved 20% toward the player's stop rate. Mostly reflects the team's defence; don't use it as a stand-alone defensive grade. From 1973-74 where every input exists.
{% enddocs %}
