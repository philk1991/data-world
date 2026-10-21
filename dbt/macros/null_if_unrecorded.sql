{#
    Null a box score stat for games where it was never recorded.

    The NBA raw tables zero-fill stats the league did not track yet (steals and
    blocks before ~1973, turnovers before ~1986, points in the paint before
    ~1997, ...), so a 0 is ambiguous. A stat that sums to 0 across every row of
    a game was not recorded for that game; a 0 alongside non-zero values from
    other rows is a real 0.

    `signal` overrides the expression used to detect an unrecorded game — e.g.
    three pointers made, where a game with no made threes is real once attempts
    were tracked.

    `attempts` / `made` add a row-level check for shooting columns: early games
    sometimes record attempts for only part of the roster, leaving 0 attempts
    next to a non-zero made count. Pass them for attempt and percentage columns.
#}
{% macro null_if_unrecorded(column, partition_by='gameId', signal=none, attempts=none, made=none) %}
    CASE
        WHEN SUM({{ signal or column }}) OVER (PARTITION BY {{ partition_by }}) = 0 THEN NULL
        {% if attempts -%}
        WHEN {{ attempts }} = 0 AND {{ made }} > 0 THEN NULL
        {% endif -%}
        ELSE {{ column }}
    END
{% endmacro %}
