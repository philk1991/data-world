{#
    The one definition of each NBA team efficiency formula
    (plans/nba-advanced-metrics-decision-log.md).

    Every macro takes count expressions rather than columns, so the same formula
    serves a single game, a season (pass SUM(...) expressions) or an as-of window.
    Always sum the raw counts over the period first and then call the macro on
    the sums; never average a per-game rate.

    Divisions go through NULLIF, so a missing or zero denominator gives NULL,
    never 0. A null count anywhere in the inputs nulls the result.

    Formulas follow Basketball-Reference (glossary, factors.html).
#}

{# One side's possession estimate: FGA + 0.4*FTA - 1.07*ORB%*(FGA - FG) + TOV. #}
{% macro nba_side_possessions(fga, fta, orb, opp_drb, fg, tov) %}
    (
        {{ fga }} + 0.4 * {{ fta }}
        - 1.07 * ({{ orb }}::DOUBLE / NULLIF({{ orb }} + {{ opp_drb }}, 0)) * ({{ fga }} - {{ fg }})
        + {{ tov }}
    )
{% endmacro %}

{# Team possessions, BBRef definition: the mean of the team's and the opponent's estimate. #}
{% macro nba_possessions(fga, fta, orb, drb, fg, tov, opp_fga, opp_fta, opp_orb, opp_drb, opp_fg, opp_tov) %}
    (
        0.5 * (
            {{ nba_side_possessions(fga, fta, orb, opp_drb, fg, tov) }}
            + {{ nba_side_possessions(opp_fga, opp_fta, opp_orb, drb, opp_fg, opp_tov) }}
        )
    )
{% endmacro %}

{# Possessions per 48 minutes. team_minutes is player-minutes (~240 a regulation game).
   Both teams share the BBRef possession estimate, so poss and opp_poss are equal. #}
{% macro nba_pace(poss, opp_poss, team_minutes) %}
    (48 * ({{ poss }} + {{ opp_poss }}) / NULLIF(2 * ({{ team_minutes }} / 5.0), 0))
{% endmacro %}

{# Points per 100 possessions (ORtg with own points, DRtg with opponent points). #}
{% macro nba_rating(pts, poss) %}
    (100 * {{ pts }} / NULLIF({{ poss }}, 0))
{% endmacro %}

{% macro nba_efg(fg, fg3, fga) %}
    (({{ fg }} + 0.5 * {{ fg3 }})::DOUBLE / NULLIF({{ fga }}, 0))
{% endmacro %}

{% macro nba_tov_pct(tov, fga, fta) %}
    ({{ tov }}::DOUBLE / NULLIF({{ fga }} + 0.44 * {{ fta }} + {{ tov }}, 0))
{% endmacro %}

{# Offensive rebound share; pass (drb, opp_orb) for defensive rebound share. #}
{% macro nba_reb_pct(reb, opp_other_reb) %}
    ({{ reb }}::DOUBLE / NULLIF({{ reb }} + {{ opp_other_reb }}, 0))
{% endmacro %}

{% macro nba_ft_rate(ft, fga) %}
    ({{ ft }}::DOUBLE / NULLIF({{ fga }}, 0))
{% endmacro %}

{% macro nba_three_par(fg3a, fga) %}
    ({{ fg3a }}::DOUBLE / NULLIF({{ fga }}, 0))
{% endmacro %}

{% macro nba_ast_rate(ast, fg) %}
    ({{ ast }}::DOUBLE / NULLIF({{ fg }}, 0))
{% endmacro %}

{% macro nba_ts(pts, fga, fta) %}
    ({{ pts }}::DOUBLE / NULLIF(2 * ({{ fga }} + 0.44 * {{ fta }}), 0))
{% endmacro %}

{# Pythagorean wins, BBRef exponent 14. #}
{% macro nba_pyth_wins(games, pts, opp_pts) %}
    (
        {{ games }} * POWER({{ pts }}::DOUBLE, 14)
        / NULLIF(POWER({{ pts }}::DOUBLE, 14) + POWER({{ opp_pts }}::DOUBLE, 14), 0)
    )
{% endmacro %}

{# ── Player formulas ──────────────────────────────────────────────────────
   Team-context rates are built as numerator / opportunity: each game adds the
   player's on-court share of the team's chances (share = MP / (Tm_MP / 5)), so a
   stint, season or career rate is SUM(numerator) / SUM(opportunity). Tm_MP is the
   team's summed player minutes for the game. Rates are 0-1, not x100. #}

{# Fraction of the team's five floor spots the player filled: MP / (Tm_MP / 5). #}
{% macro nba_on_court_share(mp, team_mp) %}
    ({{ mp }} / NULLIF({{ team_mp }} / 5.0, 0))
{% endmacro %}

{# Hollinger's Game Score. #}
{% macro nba_game_score(pts, fg, fga, ft, fta, orb, drb, stl, ast, blk, pf, tov) %}
    (
        {{ pts }} + 0.4 * {{ fg }} - 0.7 * {{ fga }} - 0.4 * ({{ fta }} - {{ ft }}) + 0.7 * {{ orb }}
        + 0.3 * {{ drb }} + {{ stl }} + 0.7 * {{ ast }} + 0.7 * {{ blk }} - 0.4 * {{ pf }} - {{ tov }}
    )
{% endmacro %}

{# ── Dean Oliver's individual ratings (Basketball-Reference ratings.html) ──
   Arguments are column prefixes: p = player totals, t = team totals, o = opponent
   totals, all over the same games, with columns named min, pts, fg, fga, fg3, ft,
   fta, orb, drb, trb, ast, stl, blk, tov, pf (team also poss). A zero FGA or FTA
   zeroes the term that divides by it. #}

{% macro _nba_div0(num, den) -%}
    COALESCE(({{ num }})::DOUBLE / NULLIF({{ den }}, 0), 0)
{%- endmacro %}

{% macro _nba_q_ast(p, t) -%}
    (
        {{ nba_on_court_share(p ~ 'min', t ~ 'min') }} * (1.14 * {{ _nba_div0(t ~ 'ast - ' ~ p ~ 'ast', t ~ 'fg') }})
        + {{ _nba_div0(
            '(' ~ t ~ 'ast / ' ~ t ~ 'min) * ' ~ p ~ 'min * 5 - ' ~ p ~ 'ast',
            '(' ~ t ~ 'fg / ' ~ t ~ 'min) * ' ~ p ~ 'min * 5 - ' ~ p ~ 'fg'
        ) }} * (1 - {{ nba_on_court_share(p ~ 'min', t ~ 'min') }})
    )
{%- endmacro %}

{# Share of a player's made field goals that were unassisted-equivalent: 1 - 0.5 * pts-per-FGA/2 * qAST. #}
{% macro _nba_fg_factor(p, t) -%}
    (1 - 0.5 * {{ _nba_div0(p ~ 'pts - ' ~ p ~ 'ft', '2 * ' ~ p ~ 'fga') }} * {{ _nba_q_ast(p, t) }})
{%- endmacro %}

{% macro _nba_ast_factor(p, t) -%}
    (0.5 * {{ _nba_div0(
        '(' ~ t ~ 'pts - ' ~ t ~ 'ft) - (' ~ p ~ 'pts - ' ~ p ~ 'ft)', '2 * (' ~ t ~ 'fga - ' ~ p ~ 'fga)'
    ) }} * {{ p }}ast)
{%- endmacro %}

{% macro _nba_tm_scoring_poss(t) -%}
    ({{ t }}fg + (1 - POWER(1 - {{ _nba_div0(t ~ 'ft', t ~ 'fta') }}, 2)) * {{ t }}fta * 0.4)
{%- endmacro %}

{% macro _nba_tm_orb_pct(t, o) -%}
    ({{ t }}orb::DOUBLE / NULLIF({{ t }}orb + ({{ o }}trb - {{ o }}orb), 0))
{%- endmacro %}

{% macro _nba_tm_play_pct(t) -%}
    ({{ _nba_tm_scoring_poss(t) }} / NULLIF({{ t }}fga + {{ t }}fta * 0.4 + {{ t }}tov, 0))
{%- endmacro %}

{% macro _nba_tm_orb_weight(t, o) -%}
    (
        ((1 - {{ _nba_tm_orb_pct(t, o) }}) * {{ _nba_tm_play_pct(t) }})
        / NULLIF(
            (1 - {{ _nba_tm_orb_pct(t, o) }}) * {{ _nba_tm_play_pct(t) }}
            + {{ _nba_tm_orb_pct(t, o) }} * (1 - {{ _nba_tm_play_pct(t) }}),
            0
        )
    )
{%- endmacro %}

{# 1 - (Tm_ORB / Tm_Scoring_Poss) * Tm_ORB_Weight * Tm_Play%: the share of scoring credit left after team offensive rebounds. #}
{% macro _nba_orb_discount(t, o) -%}
    (1 - ({{ t }}orb / NULLIF({{ _nba_tm_scoring_poss(t) }}, 0)) * {{ _nba_tm_orb_weight(t, o) }} * {{ _nba_tm_play_pct(t) }})
{%- endmacro %}

{# Individual total possessions (TotPoss). #}
{% macro nba_oliver_tot_poss(p='p_', t='t_', o='o_') %}
    (
        (
            {{ p }}fg * {{ _nba_fg_factor(p, t) }}
            + {{ _nba_ast_factor(p, t) }}
            + (1 - POWER(1 - {{ _nba_div0(p ~ 'ft', p ~ 'fta') }}, 2)) * 0.4 * {{ p }}fta
        ) * {{ _nba_orb_discount(t, o) }}
        + {{ p }}orb * {{ _nba_tm_orb_weight(t, o) }} * {{ _nba_tm_play_pct(t) }}
        + ({{ p }}fga - {{ p }}fg) * (1 - 1.07 * {{ _nba_tm_orb_pct(t, o) }})
        + CASE WHEN {{ p }}fta > 0 THEN POWER(1 - {{ p }}ft::DOUBLE / {{ p }}fta, 2) * 0.4 * {{ p }}fta ELSE 0 END
        + {{ p }}tov
    )
{% endmacro %}

{# Individual points produced (PProd). #}
{% macro nba_oliver_pprod(p='p_', t='t_', o='o_') %}
    (
        (
            2 * ({{ p }}fg + 0.5 * {{ p }}fg3) * {{ _nba_fg_factor(p, t) }}
            + 2 * {{ _nba_div0(
                t ~ 'fg - ' ~ p ~ 'fg + 0.5 * (' ~ t ~ 'fg3 - ' ~ p ~ 'fg3)', t ~ 'fg - ' ~ p ~ 'fg'
            ) }} * {{ _nba_ast_factor(p, t) }}
            + {{ p }}ft
        ) * {{ _nba_orb_discount(t, o) }}
        + {{ p }}orb * {{ _nba_tm_orb_weight(t, o) }} * {{ _nba_tm_play_pct(t) }}
        * ({{ t }}pts / NULLIF({{ _nba_tm_scoring_poss(t) }}, 0))
    )
{% endmacro %}

{# Individual defensive rating: team DRtg moved 20% toward the player's stop rate. #}
{% macro nba_oliver_drtg(p='p_', t='t_', o='o_') %}
    {%- set dor = '(' ~ o ~ 'orb::DOUBLE / NULLIF(' ~ o ~ 'orb + ' ~ t ~ 'drb, 0))' -%}
    {%- set dfg = '(' ~ o ~ 'fg::DOUBLE / NULLIF(' ~ o ~ 'fga, 0))' -%}
    {%- set fmwt -%}
        (({{ dfg }} * (1 - {{ dor }})) / NULLIF({{ dfg }} * (1 - {{ dor }}) + (1 - {{ dfg }}) * {{ dor }}, 0))
    {%- endset -%}
    {%- set stops -%}
        (
            {{ p }}stl + {{ p }}blk * {{ fmwt }} * (1 - 1.07 * {{ dor }}) + {{ p }}drb * (1 - {{ fmwt }})
            + (
                (({{ o }}fga - {{ o }}fg - {{ t }}blk) / NULLIF({{ t }}min, 0)) * {{ fmwt }} * (1 - 1.07 * {{ dor }})
                + ({{ o }}tov - {{ t }}stl) / NULLIF({{ t }}min, 0)
            ) * {{ p }}min
            + {{ _nba_div0(p ~ 'pf', t ~ 'pf') }} * 0.4 * {{ o }}fta * POWER(1 - {{ _nba_div0(o ~ 'ft', o ~ 'fta') }}, 2)
        )
    {%- endset -%}
    {%- set stop_pct = '((' ~ stops ~ ' * ' ~ o ~ 'min) / NULLIF(' ~ t ~ 'poss * ' ~ p ~ 'min, 0))' -%}
    {%- set tm_drtg = '(100 * ' ~ o ~ 'pts / NULLIF(' ~ t ~ 'poss, 0))' -%}
    {%- set d_pts_per_scposs -%}
        ({{ o }}pts / NULLIF({{ o }}fg + (1 - POWER(1 - {{ _nba_div0(o ~ 'ft', o ~ 'fta') }}, 2)) * {{ o }}fta * 0.4, 0))
    {%- endset -%}
    ({{ tm_drtg }} + 0.2 * (100 * {{ d_pts_per_scposs }} * (1 - {{ stop_pct }}) - {{ tm_drtg }}))
{% endmacro %}
