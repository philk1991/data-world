{#
    Decode season and game type from an NBA game id.

    NBA game ids are 00TYYNNNNN: T is the game type, YY the last two digits of
    the season's start year, NNNNN a sequence number. The raw tables store them
    as BIGINT, which drops the leading zeros (21901232 = Regular Season 2019-20).

    The id is the league's own season assignment, so it handles calendar
    anomalies a date cutoff gets wrong: the 2020 bubble (seeding games and
    playoffs, July-October 2020) belongs to 2019-20, and the July 2021 Finals to
    2020-21. It is also complete and consistent where the raw gameType column is
    not (null for most 2021-22 team box scores, "Pre Season" vs "Preseason",
    2023-24 NBA Cup group games labelled as the Cup although they count as
    regular season).
#}

{# Seasons span 1946-47 onward, so YY below 46 is 20YY. Breaks in 2046. #}
{% macro nba_season_start_year(game_id) %}
    (({{ game_id }} // 100000) % 100 + CASE WHEN ({{ game_id }} // 100000) % 100 >= 46 THEN 1900 ELSE 2000 END)
{% endmacro %}

{# NBA Cup group and knockout games carry type 2 and count toward the standings; only the final (type 6) does not. #}
{% macro nba_game_type(game_id) %}
    CASE {{ game_id }} // 10000000
        WHEN 1 THEN 'Preseason'
        WHEN 2 THEN 'Regular Season'
        WHEN 3 THEN 'All-Star Game'
        WHEN 4 THEN 'Playoffs'
        WHEN 5 THEN 'Play-in Tournament'
        WHEN 6 THEN 'NBA Cup Final'
    END
{% endmacro %}
