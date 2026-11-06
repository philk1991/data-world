{% set counts = [
    'field_goals_made', 'field_goals_attempted', 'three_pointers_made', 'three_pointers_attempted',
    'free_throws_made', 'free_throws_attempted', 'rebounds_offensive', 'rebounds_defensive',
    'rebounds_total', 'assists', 'steals', 'blocks', 'turnovers', 'fouls_personal'
] %}
{# Shooting pairs with more makes than attempts are impossible: null both. #}
{% macro consistent_shooting() -%}
* REPLACE (
    CASE WHEN field_goals_made > field_goals_attempted THEN NULL ELSE field_goals_made END AS field_goals_made,
    CASE WHEN field_goals_made > field_goals_attempted THEN NULL ELSE field_goals_attempted END
        AS field_goals_attempted,
    CASE WHEN three_pointers_made > three_pointers_attempted THEN NULL ELSE three_pointers_made END
        AS three_pointers_made,
    CASE WHEN three_pointers_made > three_pointers_attempted THEN NULL ELSE three_pointers_attempted END
        AS three_pointers_attempted,
    CASE WHEN free_throws_made > free_throws_attempted THEN NULL ELSE free_throws_made END AS free_throws_made,
    CASE WHEN free_throws_made > free_throws_attempted THEN NULL ELSE free_throws_attempted END
        AS free_throws_attempted
)
{%- endmacro %}
{# A count summed from the team's player rows, kept only when the sum is complete. #}
{% macro player_sum(c) -%}
CASE WHEN p.{{ c }}_rows = p.players AND p.points = t.team_score THEN p.{{ c }} END
{%- endmacro %}
-- One row per team per competitive game (Regular Season, Play-in Tournament,
-- Playoffs, NBA Cup Final) with the team's and the opponent's box counts side by
-- side (opponent columns prefixed opp_), the foundation for every team metric.
--
-- Counts come from the team box score. Before 1983-84 the team box carries
-- scores only, so each count falls back to the sum of the team's player rows for
-- that game, but only when the sum is complete: the players' points add up to
-- the team score and no player who played has that count missing. Otherwise the
-- count stays null; it is never zero-filled. counts_source records which applied
-- (field goal attempts decide it). Player sums leave out team rebounds and team
-- turnovers, so they run slightly low.
-- Three-pointers are 0, not null, before 1979-80: the shot did not exist.
-- Total rebounds are offensive + defensive wherever both resolve (from either
-- source): the 1984-85 team box has totals but no split, and its totals add ~6
-- team rebounds a game that the player-summed split leaves out.
-- A shooting pair with more makes than attempts is impossible and is nulled:
-- first in the team box (a few 1959-62 box scores record only part of the
-- attempts), so it can fall back to the player sum, then again after the
-- fallback (some early player rows are inconsistent too). counts_source becomes
-- none when the field goal pair is dropped.
-- team_minutes is the team box's player-minutes (240 a regulation game, +25 per
-- overtime). Where the team box records 0 (before 1964-65, and a few current
-- games) it falls back to the players' summed minutes rounded to 240 + 25 per
-- overtime (player minutes are truncated to whole minutes, so they sum to ~235);
-- null when neither exists.
WITH team_box_source AS (
    SELECT *
    FROM
        {{ ref('stg_nba_team_statistics') }}
),

player_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_games') }}
),

-- Transform
team_box AS (
    SELECT
        {{ consistent_shooting() }}
    FROM
        team_box_source
),

player_sums AS (
    SELECT
        game_id,
        team_id,
        {% for c in counts %}
        SUM({{ c }}) AS {{ c }},
        COUNT({{ c }}) AS {{ c }}_rows,
        {% endfor %}
        SUM(points) AS points,
        SUM(minutes_played) AS minutes_played,
        COUNT(*) AS players
    FROM
        player_games
    GROUP BY
        game_id, team_id
),

team_side AS (
    SELECT
        t.game_id,
        t.team_id,
        t.opponent_team_id,
        t.season_start_year,
        t.game_type,
        t.game_date,
        t.is_home,
        t.is_win,
        t.team_score AS points,
        t.opponent_score AS opp_points,
        COALESCE(
            NULLIF(t.minutes_played, 0),
            240 + 25 * GREATEST(ROUND((NULLIF(p.minutes_played, 0) - 240) / 25), 0)
        ) AS team_minutes,
        t.points_in_the_paint,
        t.points_fast_break,
        {% for c in counts %}
        {% if c.startswith('three_pointers') %}
        CASE
            WHEN t.season_start_year < 1979 THEN 0
            ELSE COALESCE(t.{{ c }}, {{ player_sum(c) }})
        END AS {{ c }},
        {% elif c == 'rebounds_total' %}
        COALESCE(
            COALESCE(t.rebounds_offensive, {{ player_sum('rebounds_offensive') }})
            + COALESCE(t.rebounds_defensive, {{ player_sum('rebounds_defensive') }}),
            t.rebounds_total,
            {{ player_sum(c) }}
        ) AS rebounds_total,
        {% else %}
        COALESCE(t.{{ c }}, {{ player_sum(c) }}) AS {{ c }},
        {% endif %}
        {% endfor %}
        CASE
            WHEN t.field_goals_attempted IS NOT NULL THEN 'team_box'
            WHEN p.field_goals_attempted_rows = p.players AND p.points = t.team_score THEN 'player_sum'
            ELSE 'none'
        END AS counts_source
    FROM
        team_box t
    LEFT JOIN
        player_sums p
        USING (game_id, team_id)
    WHERE
        t.game_type IN ('Regular Season', 'Play-in Tournament', 'Playoffs', 'NBA Cup Final')
),

checked AS (
    SELECT
        {{ consistent_shooting() }}
    FROM
        team_side
),

resolved AS (
    SELECT
        * REPLACE (
            CASE WHEN field_goals_attempted IS NULL THEN 'none' ELSE counts_source END AS counts_source,
            -- A handful of 1953-83 games record more assists than made field goals.
            CASE WHEN assists > field_goals_made THEN NULL ELSE assists END AS assists
        )
    FROM
        checked
),

paired AS (
    SELECT
        t.*,
        {% for c in counts %}
        o.{{ c }} AS opp_{{ c }},
        {% endfor %}
        o.team_minutes AS opp_team_minutes,
        o.counts_source AS opp_counts_source
    FROM
        resolved t
    LEFT JOIN
        resolved o
        ON
            t.game_id = o.game_id
            AND t.opponent_team_id = o.team_id
)

-- AM04 is suppressed: SQLFluff can't count columns through the * REPLACE stages.
SELECT
    *,  -- noqa: AM04
    -- GREATEST skips nulls, so guard the null explicitly.
    CASE WHEN team_minutes IS NOT NULL THEN ROUND(GREATEST(team_minutes - 240, 0) / 25) END AS overtime_periods,
    team_minutes IS NOT NULL
    AND field_goals_attempted IS NOT NULL
    AND free_throws_attempted IS NOT NULL
    AND rebounds_offensive IS NOT NULL
    AND rebounds_defensive IS NOT NULL
    AND turnovers IS NOT NULL
    AND opp_field_goals_attempted IS NOT NULL
    AND opp_free_throws_attempted IS NOT NULL
    AND opp_rebounds_offensive IS NOT NULL
    AND opp_rebounds_defensive IS NOT NULL
    AND opp_turnovers IS NOT NULL AS has_full_box,
    {{
        nba_possessions(
            'field_goals_attempted', 'free_throws_attempted', 'rebounds_offensive', 'rebounds_defensive',
            'field_goals_made', 'turnovers',
            'opp_field_goals_attempted', 'opp_free_throws_attempted', 'opp_rebounds_offensive',
            'opp_rebounds_defensive', 'opp_field_goals_made', 'opp_turnovers'
        )
    }} AS possessions
FROM
    paired
