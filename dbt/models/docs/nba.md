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
Regular season games with advanced box score data that season.
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

{% docs nba__assist_pct__team %}
Share of the team's made field goals that were assisted, 0-1.
{% enddocs %}
