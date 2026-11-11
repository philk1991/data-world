{% set turnovers_start = nba_coverage_start('turnovers') %}
{% set oliver = {
    'min': ('minutes_played', 'team_player_minutes', 'team_player_minutes'),
    'pts': ('points', 'team_points', 'opp_points'),
    'fg': ('field_goals_made', 'team_field_goals_made', 'opp_field_goals_made'),
    'fga': ('field_goals_attempted', 'team_field_goals_attempted', 'opp_field_goals_attempted'),
    'fg3': ('three_pointers_made', 'team_three_pointers_made', none),
    'ft': ('free_throws_made', 'team_free_throws_made', 'opp_free_throws_made'),
    'fta': ('free_throws_attempted', 'team_free_throws_attempted', 'opp_free_throws_attempted'),
    'orb': ('rebounds_offensive', 'team_rebounds_offensive', 'opp_rebounds_offensive'),
    'drb': ('rebounds_defensive', 'team_rebounds_defensive', 'opp_rebounds_defensive'),
    'trb': ('rebounds_total', 'team_rebounds_total', 'opp_rebounds_total'),
    'ast': ('assists', 'team_assists', none),
    'stl': ('steals', 'team_steals', none),
    'blk': ('blocks', 'team_blocks', none),
    'tov': ('turnovers', 'team_turnovers', 'opp_turnovers'),
    'pf': ('fouls_personal', 'team_fouls_personal', none),
    'poss': (none, 'team_possessions', none)
} %}
-- One row per player per team per season per game type (a stint: a traded
-- player has one per team), holding the sums every player metric is computed
-- from; nba_player_stint_advanced and nba_player_season_advanced turn them into
-- rates with the same macro (nba_player_metric_columns).
-- Rate numerators are summed only over games where their opportunity exists, so
-- each pair covers the same games. Dean Oliver's individual ratings are computed
-- here from stint totals (single games are too noisy): p_ / t_ / o_ columns are
-- the player's, team's and opponent's totals over the games the player played
-- for the team that have every input (rating_games), from 1973-74.
-- Points produced and individual possessions need player turnovers (1977-78 on).
WITH context AS (
    SELECT *
    FROM
        {{ ref('int_nba_player_game_context') }}
),

-- Transform
flagged AS (
    SELECT
        *,
        season_start_year >= {{ nba_coverage_start('possessions') }}
        AND team_possessions IS NOT NULL
        AND COALESCE(minutes_played, 0) > 0
        AND on_court_share IS NOT NULL
        {% for stat, cols in oliver.items() %}
        {% for col in cols %}
        {% if col %}
        AND {{ col }} IS NOT NULL
        {% endif %}
        {% endfor %}
        {% endfor %}
            AS has_rating_inputs
    FROM
        context
),

stints AS (
    SELECT
        person_id,
        team_id,
        season_start_year,
        game_type,
        COUNT(*) AS games_played,
        SUM(minutes_played) AS minutes_played,
        SUM(points) AS points,
        -- Shooting and rate inputs, matched pairs from macros/nba_metrics.sql.
        {{ nba_shooting_components('SUM') }},
        {{ nba_player_rate_components('SUM') }},
        -- Shooting: made shots only where the attempts were recorded.
        SUM(field_goals_made) FILTER (WHERE field_goals_attempted IS NOT NULL) AS field_goals_made,
        SUM(field_goals_attempted) AS field_goals_attempted,
        SUM(three_pointers_made) FILTER (WHERE field_goals_attempted IS NOT NULL) AS three_pointers_made,
        SUM(three_pointers_attempted) FILTER (WHERE field_goals_attempted IS NOT NULL) AS three_pointers_attempted,
        SUM(free_throws_made) FILTER (WHERE field_goals_attempted IS NOT NULL) AS ft_rate_free_throws_made,
        SUM(field_goals_attempted) FILTER (WHERE free_throws_made IS NOT NULL) AS ft_rate_field_goals_attempted,
        SUM(game_score) AS game_score,
        COUNT(game_score) AS game_score_games,
        -- Oliver rating inputs.
        {% for stat, cols in oliver.items() %}
        {% for col in cols %}
        {% if col %}
        SUM({{ col }}) FILTER (WHERE has_rating_inputs) AS {{ ['p_', 't_', 'o_'][loop.index0] }}{{ stat }},
        {% endif %}
        {% endfor %}
        {% endfor %}
        SUM(player_possessions) FILTER (WHERE has_rating_inputs) AS rating_player_possessions,
        COUNT(*) FILTER (WHERE has_rating_inputs) AS rating_games
    FROM
        flagged
    GROUP BY
        person_id, team_id, season_start_year, game_type
)

SELECT
    *,
    CASE WHEN season_start_year >= {{ turnovers_start }} THEN {{ nba_oliver_pprod() }} END AS points_produced,
    CASE
        WHEN season_start_year >= {{ turnovers_start }} THEN {{ nba_oliver_tot_poss() }}
    END AS individual_possessions,
    {{ nba_oliver_drtg() }} AS individual_defensive_rating
FROM
    stints
