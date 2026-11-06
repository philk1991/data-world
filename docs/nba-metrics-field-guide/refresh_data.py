"""Refresh the data embedded in the NBA Metrics Field Guide (index.html beside this file).

Reads the lake read-only and rewrites the page's <script id="guide-data"> block with:
  - samples: example rows from the last completed season (SEASON) for each new mart
  - profiles: DuckDB SUMMARIZE output (descriptive statistics per column) for the
    twelve new or rebuilt NBA metric models, across all seasons

Run after a dbt build that changes the NBA metric models: `task docs:nba-guide`.
The page's prose (validation figures, example query results, data quirks) is
hand-written and is not refreshed; update it alongside the models when they change.
SUMMARIZE's quartiles are approximate and its means sum in parallel, so re-running
on unchanged data can shift those statistics in the last digits.

Usage (from data-ingestion/, with it on PYTHONPATH so lake.py imports):
    PYTHONPATH=. python ../docs/nba-metrics-field-guide/refresh_data.py [path/to/index.html]
"""

import datetime
import decimal
import json
import math
import re
import sys
from pathlib import Path

from lake import connect_lake

# season_start_year of the last completed season (2025 = 2025-26).
SEASON = 2025

PROFILED_MODELS = [
    "intermediate_nba.int_nba_player_games",
    "intermediate_nba.int_nba_team_games",
    "intermediate_nba.int_nba_team_season_srs",
    "intermediate_nba.int_nba_player_game_context",
    "intermediate_nba.int_nba_player_stints",
    "marts.nba_team_game_stats",
    "marts.nba_league_season_baselines",
    "marts.nba_team_advanced_profile",
    "marts.nba_team_form",
    "marts.nba_player_stint_advanced",
    "marts.nba_player_season_advanced",
    "marts.nba_player_advanced_career",
]

# One sample per mart; the page's "Last season" tabs read these keys.
SAMPLE_QUERIES = {
    "nba_team_advanced_profile": """
        SELECT d.current_team_abbrev AS team, p.wins, p.losses, p.offensive_rating, p.defensive_rating,
               p.net_rating, p.pace, p.effective_field_goal_pct, p.turnover_pct, p.offensive_rebound_pct,
               p.free_throw_rate, p.opp_effective_field_goal_pct, p.pythagorean_wins, p.luck_wins,
               p.simple_rating_system, p.strength_of_schedule, p.relative_offensive_rating,
               p.three_point_attempt_rate, p.coverage_flag
        FROM marts.nba_team_advanced_profile p
        JOIN marts.nba_team_dim d ON p.team_id = d.team_id
        WHERE p.season_start_year = {season} AND p.game_type = 'Regular Season'
        ORDER BY p.net_rating DESC""",
    "nba_league_season_baselines": """
        SELECT game_type, team_games, lg_points_per_game, lg_pace, lg_offensive_rating,
               lg_points_per_possession, lg_true_shooting_pct, lg_effective_field_goal_pct,
               lg_three_point_attempt_rate, lg_free_throw_rate, lg_turnover_pct, lg_offensive_rebound_pct
        FROM marts.nba_league_season_baselines
        WHERE season_start_year = {season}
        ORDER BY team_games DESC""",
    "nba_player_season_advanced": """
        SELECT s.first_name || ' ' || s.last_name AS player, d.current_team_abbrev AS team, s.games_played,
               s.total_minutes, s.total_points, s.true_shooting_pct, s.usage_pct, s.assist_pct, s.rebound_pct,
               s.steal_pct, s.block_pct, s.turnover_pct, s.points_per_100, s.game_score_per_game,
               s.true_shooting_points_added, s.individual_offensive_rating, s.individual_defensive_rating,
               s.is_multi_team
        FROM marts.nba_player_season_advanced s
        JOIN marts.nba_team_dim d ON s.primary_team_id = d.team_id
        WHERE s.season_start_year = {season} AND s.game_type = 'Regular Season' AND s.total_minutes >= 1500
        ORDER BY s.game_score_per_game DESC
        LIMIT 30""",
    "nba_player_stint_advanced": """
        SELECT st.first_name || ' ' || st.last_name AS player, d.current_team_abbrev AS team, st.games_played,
               st.total_minutes, st.true_shooting_pct, st.usage_pct, st.assist_pct, st.rebound_pct,
               st.points_per_100, st.individual_offensive_rating, st.individual_defensive_rating
        FROM marts.nba_player_stint_advanced st
        JOIN marts.nba_team_dim d ON st.team_id = d.team_id
        JOIN marts.nba_player_season_advanced se
            ON se.person_id = st.person_id
            AND se.season_start_year = st.season_start_year
            AND se.game_type = st.game_type
        WHERE st.season_start_year = {season} AND st.game_type = 'Regular Season'
            AND se.is_multi_team AND se.total_minutes >= 1200
        ORDER BY se.total_minutes DESC, st.person_id, st.games_played DESC
        LIMIT 16""",
    "nba_team_game_stats": """
        SELECT g.game_date, d.current_team_abbrev AS team, g.is_home, g.points, g.opp_points, g.possessions,
               g.pace, g.offensive_rating, g.defensive_rating, g.effective_field_goal_pct, g.turnover_pct,
               g.offensive_rebound_pct, g.free_throw_rate, g.three_point_attempt_rate, g.counts_source
        FROM marts.nba_team_game_stats g
        JOIN marts.nba_team_dim d ON g.team_id = d.team_id
        WHERE g.game_id = (
            SELECT MAX_BY(game_id, game_date) FROM marts.nba_team_game_stats
            WHERE season_start_year = {season} AND game_type = 'Playoffs'
        )
        ORDER BY g.is_home DESC""",
    "nba_team_form": """
        SELECT d.current_team_abbrev AS team, f.game_date, f.last_10_games, f.last_10_net_rating,
               f.last_20_net_rating, f.season_to_date_games, f.season_to_date_net_rating,
               f.league_to_date_offensive_rating, f.league_to_date_pace
        FROM marts.nba_team_form f
        JOIN marts.nba_team_dim d ON f.team_id = d.team_id
        WHERE f.season_start_year = {season} AND f.game_type = 'Regular Season'
        QUALIFY ROW_NUMBER() OVER (PARTITION BY f.team_id ORDER BY f.game_date DESC) = 1
        ORDER BY f.last_10_net_rating DESC""",
}

DATA_BLOCK = re.compile(r'(<script type="application/json" id="guide-data">).*?(</script>)', re.S)


def query(conn, sql: str) -> dict:
    """Run a query and return {"columns": [...], "rows": [[...], ...]}."""
    cursor = conn.execute(sql)
    return {"columns": [d[0] for d in cursor.description], "rows": [list(r) for r in cursor.fetchall()]}


def to_json_value(value):
    """Make a DuckDB value JSON-safe: round floats, drop NaN/inf, stringify dates."""
    if isinstance(value, dict):
        return {k: to_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_json_value(v) for v in value]
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else round(value, 4)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def collect(conn) -> dict:
    profiles = {}
    for table in PROFILED_MODELS:
        schema, name = table.split(".")
        row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        profiles[name] = {"schema": schema, "row_count": row_count, **query(conn, f"SUMMARIZE {table}")}
        print(f"  profiled {table}: {row_count:,} rows", file=sys.stderr)
    samples = {name: query(conn, sql.format(season=SEASON)) for name, sql in SAMPLE_QUERIES.items()}
    season_label = f"{SEASON}-{str(SEASON + 1)[2:]}"
    return {"season": season_label, "samples": samples, "profiles": profiles}


def main() -> int:
    page = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("index.html")
    html = page.read_text()
    if not DATA_BLOCK.search(html):
        print(f"No guide-data block found in {page}", file=sys.stderr)
        return 1
    data = collect(connect_lake(read_only=True))
    # "</" inside a <script> block would end it early.
    payload = json.dumps(to_json_value(data), separators=(",", ":")).replace("</", "<\\/")
    page.write_text(DATA_BLOCK.sub(lambda m: m.group(1) + payload + m.group(2), html, count=1))
    print(f"Refreshed {page} ({len(payload) // 1024} KB of data)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
