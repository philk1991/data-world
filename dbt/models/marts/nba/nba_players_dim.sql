-- Conformed player dimension: one row per person_id carrying biography (age,
-- height, weight, position, draft, origin) plus the span of competitive games
-- played (Regular Season, Playoffs, Play-in Tournament and NBA Cup Final; only
-- games actually played count). Covers every player in stg_nba_players and every
-- player in the box scores; box-score-only players take their name from their
-- latest box score and have null bio. Ages are completed years, so they are only
-- as good as birth_date (null for placeholder dates, see stg_nba_players).
WITH players AS (
    SELECT *
    FROM
        {{ ref('stg_nba_players') }}
),

box_scores AS (
    SELECT *
    FROM
        {{ ref('stg_nba_player_statistics') }}
),

-- Transform
box_score_names AS (
    SELECT
        person_id,
        first_name,
        last_name
    FROM
        box_scores
    WHERE
        person_id IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY game_date DESC, game_id DESC) = 1
),

career_span AS (
    SELECT
        person_id,
        MIN(game_date) AS first_game_date,
        MAX(game_date) AS last_game_date,
        MIN(season_start_year) AS first_season_start_year,
        MAX(season_start_year) AS last_season_start_year,
        COUNT(DISTINCT season_start_year) AS seasons_played
    FROM
        box_scores
    WHERE
        person_id IS NOT NULL
        AND minutes_played IS NOT NULL
        AND game_type IN ('Regular Season', 'Playoffs', 'Play-in Tournament', 'NBA Cup Final')
    GROUP BY
        person_id
),

latest_season AS (
    SELECT MAX(last_season_start_year) AS latest_season_start_year
    FROM
        career_span
),

all_players AS (
    SELECT person_id
    FROM
        players
    UNION
    SELECT person_id
    FROM
        box_score_names
)

SELECT
    ap.person_id,
    COALESCE(p.first_name, bn.first_name) AS first_name,
    COALESCE(p.last_name, bn.last_name) AS last_name,
    NULLIF(CONCAT_WS(' ', COALESCE(p.first_name, bn.first_name), COALESCE(p.last_name, bn.last_name)), '')
        AS player_name,
    p.person_id IS NOT NULL AS has_bio_record,
    p.birth_date,
    p.height_inches,
    ROUND(p.height_inches * 2.54, 1)::DOUBLE AS height_cm,
    (p.height_inches // 12)::VARCHAR || '-' || (p.height_inches % 12)::VARCHAR AS height_feet_inches,
    p.body_weight_lbs,
    ROUND(p.body_weight_lbs * 0.45359237, 1)::DOUBLE AS body_weight_kg,
    p.is_guard,
    p.is_forward,
    p.is_center,
    NULLIF(
        CONCAT_WS(
            '-',
            CASE WHEN p.is_guard THEN 'G' END,
            CASE WHEN p.is_forward THEN 'F' END,
            CASE WHEN p.is_center THEN 'C' END
        ),
        ''
    ) AS position,
    p.school,
    p.country,
    p.is_undrafted,
    p.draft_year,
    p.draft_round,
    p.draft_number,
    cs.first_game_date,
    cs.last_game_date,
    cs.first_season_start_year,
    cs.last_season_start_year,
    cs.seasons_played,
    -- Two seasons, so the proxy still holds in the first weeks of a new season
    cs.last_season_start_year >= ls.latest_season_start_year - 1 AS played_in_last_two_seasons,
    DATE_SUB('year', p.birth_date, cs.first_game_date) AS age_at_first_game,
    DATE_SUB('year', p.birth_date, cs.last_game_date) AS age_at_last_game
FROM
    all_players ap
LEFT JOIN
    players p
    USING (person_id)
LEFT JOIN
    box_score_names bn
    USING (person_id)
LEFT JOIN
    career_span cs
    USING (person_id)
CROSS JOIN
    latest_season ls
ORDER BY
    ap.person_id
