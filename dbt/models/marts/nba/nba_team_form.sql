-- One row per team per competitive game: the team's form going into that game,
-- using only games played before it (as of tip-off; the game itself never counts).
-- Last-10, last-20 and season-to-date net rating come from summed points and
-- possessions over the window, within the same season and game type, so playoff
-- form has its own baseline. League-to-date offensive rating and pace use every
-- team's games on earlier dates of the same season and game type, so form is
-- compared with this season's league so far, not last season's (pace usually
-- slows and efficiency rises as a season goes on).
-- 1973-74 onward (possessions need offensive rebounds and turnovers); windows
-- skip games without a full box. *_games columns give each window's sample size.
WITH team_games AS (
    SELECT *
    FROM
        {{ ref('int_nba_team_games') }}
),

-- Transform
rated AS (
    SELECT
        team_id,
        game_id,
        season_start_year,
        game_type,
        game_date,
        CASE WHEN has_full_box THEN points END AS points,
        CASE WHEN has_full_box THEN opp_points END AS opp_points,
        CASE WHEN has_full_box THEN possessions END AS possessions,
        CASE WHEN has_full_box THEN team_minutes END AS team_minutes
    FROM
        team_games
    WHERE
        season_start_year >= {{ nba_coverage_start('possessions') }}
),

windows AS (
    SELECT
        *,
        {% for n in [10, 20] %}
        COUNT(possessions) OVER last_{{ n }} AS last_{{ n }}_games,
        SUM(points) OVER last_{{ n }} AS last_{{ n }}_points,
        SUM(opp_points) OVER last_{{ n }} AS last_{{ n }}_opp_points,
        SUM(possessions) OVER last_{{ n }} AS last_{{ n }}_possessions,
        {% endfor %}
        COUNT(possessions) OVER to_date AS season_games,
        SUM(points) OVER to_date AS season_points,
        SUM(opp_points) OVER to_date AS season_opp_points,
        SUM(possessions) OVER to_date AS season_possessions
    FROM
        rated
    WINDOW
        team_season AS (PARTITION BY team_id, season_start_year, game_type ORDER BY game_date, game_id),
        last_10 AS (team_season ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING),
        last_20 AS (team_season ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING),
        to_date AS (team_season ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
),

-- League totals per date, accumulated so each date sees only earlier dates.
league_daily AS (
    SELECT
        season_start_year,
        game_type,
        game_date,
        SUM(points) AS points,
        SUM(possessions) AS possessions,
        SUM(team_minutes) AS team_minutes
    FROM
        rated
    WHERE
        possessions IS NOT NULL
    GROUP BY
        season_start_year, game_type, game_date
),

league_to_date AS (
    SELECT
        season_start_year,
        game_type,
        game_date,
        SUM(points) OVER before_date AS points,
        SUM(possessions) OVER before_date AS possessions,
        SUM(team_minutes) OVER before_date AS team_minutes
    FROM
        league_daily
    WINDOW
        before_date AS (
            PARTITION BY season_start_year, game_type ORDER BY game_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )
)

SELECT
    w.team_id,
    w.game_id,
    w.season_start_year,
    w.game_type,
    w.game_date,
    w.last_10_games,
    ROUND(
        {{ nba_rating('w.last_10_points', 'w.last_10_possessions') }}
        - {{ nba_rating('w.last_10_opp_points', 'w.last_10_possessions') }}, 1
    ) AS last_10_net_rating,
    w.last_20_games,
    ROUND(
        {{ nba_rating('w.last_20_points', 'w.last_20_possessions') }}
        - {{ nba_rating('w.last_20_opp_points', 'w.last_20_possessions') }}, 1
    ) AS last_20_net_rating,
    w.season_games AS season_to_date_games,
    ROUND(
        {{ nba_rating('w.season_points', 'w.season_possessions') }}
        - {{ nba_rating('w.season_opp_points', 'w.season_possessions') }}, 1
    ) AS season_to_date_net_rating,
    ROUND({{ nba_rating('l.points', 'l.possessions') }}, 1) AS league_to_date_offensive_rating,
    ROUND({{ nba_pace('l.possessions', 'l.possessions', 'l.team_minutes') }}, 1) AS league_to_date_pace,
    '{{ var("nba_metrics_version") }}' AS formula_version
FROM
    windows w
LEFT JOIN
    league_to_date l
    ON
        w.season_start_year = l.season_start_year
        AND w.game_type = l.game_type
        AND w.game_date = l.game_date
