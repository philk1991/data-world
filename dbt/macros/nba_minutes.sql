{#
    Parse a player's numMinutes into decimal minutes.

    From 2024-25 the source mostly writes minutes as mm.ss (19.38 = 19 min 38 s),
    then switches to true decimal minutes in late 2025-26 and 2026-27; earlier
    seasons hold whole (truncated) minutes. The format is consistent within one
    team's box score for a game, so each team-game is read as mm.ss when every
    fractional part is below .60 and the mm.ss reading sums to a full game
    (240 + 25 per overtime, within half a minute); otherwise the value is taken
    as decimal. Whole-minute values read the same either way.

    `partition_by` names the columns that identify one team's box score.
#}
{% macro nba_minutes(column, partition_by) %}
    {%- set raw = 'TRY_CAST(' ~ column ~ ' AS DOUBLE)' -%}
    {%- set mmss = 'FLOOR(' ~ raw ~ ') + (' ~ raw ~ ' - FLOOR(' ~ raw ~ ')) * 100 / 60' -%}
    CASE
        WHEN
            MAX({{ raw }} - FLOOR({{ raw }})) OVER (PARTITION BY {{ partition_by }}) < 0.595
            AND ABS(
                SUM({{ mmss }}) OVER (PARTITION BY {{ partition_by }})
                - (240 + 25 * GREATEST(ROUND((SUM({{ mmss }}) OVER (PARTITION BY {{ partition_by }}) - 240) / 25), 0))
            ) <= 0.5
            THEN {{ mmss }}
        ELSE {{ raw }}
    END
{% endmacro %}
