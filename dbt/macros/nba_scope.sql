{#
    Which games, seasons and metric eras an NBA model covers. Every model takes
    these from here instead of repeating the lists and years
    (plans/adr/0001-career-scope.md, plans/adr/0003-coverage-cutoff.md).
#}

{# "2023-24" from 2023. #}
{% macro nba_season_label(season_start_year) %}
    ({{ season_start_year }}::VARCHAR || '-' || RIGHT(({{ season_start_year }} + 1)::VARCHAR, 2))
{% endmacro %}

{# Games that count: the standings, the play-in and the playoffs, plus the Cup final.
   Preseason and All-Star games are exhibitions. #}
{% macro nba_competitive_game_types() %}
    ('Regular Season', 'Play-in Tournament', 'Playoffs', 'NBA Cup Final')
{% endmacro %}

{# The game types a career is reported for, each on its own row so they can be added
   together. Play-in and Cup final games count toward neither, as on NBA.com. #}
{% macro nba_career_game_types() %}
    ('Regular Season', 'Playoffs')
{% endmacro %}

{# The first season with a complete schedule. The source holds only the 30 current
   franchises, so games against defunct teams are missing before 1954-55. #}
{% macro nba_first_complete_season() %}
    {{ var('nba_first_complete_season') }}
{% endmacro %}

{# The first season a stat or metric family was recorded (decision log, source check 3).
   Metrics are null before it. #}
{% macro nba_coverage_start(family) %}
    {%- set starts = {
        'assists': 1964,
        'total_rebounds': 1964,
        'rebound_split': 1973,
        'steals_blocks': 1973,
        'possessions': 1973,
        'turnovers': 1977,
        'three_pointers': 1979,
    } -%}
    {%- if family not in starts -%}
        {{ exceptions.raise_compiler_error("nba_coverage_start: unknown family '" ~ family ~ "'") }}
    {%- endif -%}
    {{ starts[family] }}
{%- endmacro %}

{# True when a player made enough shots to rank on a shooting leaderboard: the NBA's
   per-stat minimum (300 field goals, 82 threes, 125 free throws made since 2013-14),
   scaled to the games the team played, as the league prorated 2019-20 and 2020-21.
   Field goals also gate eFG% and true shooting. Null when the makes weren't recorded. #}
{% macro nba_shooting_qualified(stat, makes, team_games) %}
    {%- set minimums = {
        'field_goals': 300,
        'three_pointers': 82,
        'free_throws': 125,
    } -%}
    {%- if stat not in minimums -%}
        {{ exceptions.raise_compiler_error("nba_shooting_qualified: unknown stat '" ~ stat ~ "'") }}
    {%- endif -%}
    ({{ makes }} >= {{ minimums[stat] }} * {{ team_games }} / 82.0)
{%- endmacro %}
