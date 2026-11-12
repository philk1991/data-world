"""Check that the Cube views give the same numbers as the dbt rollup marts.

The rollup marts are kept as convenience tables for SQL users (ADR 0004) and
Cube computes the same rates from additive components (ADR 0002), so every
kept rollup must agree with Cube on every row. Each case below runs one Cube
query grouped to the mart's grain and the matching SELECT on the mart, then
compares them key by key: rows on one side only, nulls on one side only, and
values that differ by more than floating-point noise. Marts are unrounded, so
the tolerance is tight.

Needs the Cube dev server (`task cube:dev`) and the lake. Exits 1 on any
difference. Run with `task cube:reconcile`.
"""

import base64
import hashlib
import hmac
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data-ingestion"))
from lake import connect_lake  # noqa: E402

_config = {**dotenv_values(ROOT / "cube" / ".env"), **os.environ}
API_URL = _config.get("CUBE_API_URL", "http://localhost:4000/cubejs-api/v1").rstrip("/")
API_SECRET = _config.get("CUBEJS_API_SECRET")

PAGE_SIZE = 10_000
# Both sides sum the same doubles in a different order, so they agree to about
# 1e-12; anything past this is a real difference.
REL_TOL = 1e-9
ABS_TOL = 1e-9

# The cubes keep seasons from 1954-55 (nba_first_complete_season, ADR 0003)
# and the team views only competitive games.
FIRST_SEASON = 1954
COMPETITIVE = ["Regular Season", "Play-in Tournament", "Playoffs", "NBA Cup Final"]
MART_SCOPE = f"season_start_year >= {FIRST_SEASON} AND game_type IN ({', '.join(repr(t) for t in COMPETITIVE)})"


@dataclass
class Case:
    name: str
    view: str
    keys: list[str]  # Cube dimension = mart column
    columns: dict[str, str]  # Cube measure -> mart column
    mart: str
    mart_where: str
    game_types: list[str] = field(default_factory=lambda: COMPETITIVE)


CASES = [
    Case(
        name="player careers",
        view="player_career",
        keys=["person_id", "game_type"],
        columns={
            "count_seasons": "seasons_played",
            "first_season_start_year": "first_season_start_year",
            "last_season_start_year": "last_season_start_year",
            "sum_games_played": "games_played",
            "sum_total_points": "total_points",
            "sum_total_rebounds": "total_rebounds",
            "sum_total_assists": "total_assists",
            "sum_total_steals": "total_steals",
            "sum_total_blocks": "total_blocks",
            "sum_total_turnovers": "total_turnovers",
            "sum_field_goals_made": "total_field_goals_made",
            "sum_field_goals_attempted": "total_field_goals_attempted",
            "sum_three_pointers_made": "total_three_pointers_made",
            "sum_free_throws_made": "total_free_throws_made",
            "points_per_game": "points_per_game",
            "rebounds_per_game": "rebounds_per_game",
            "assists_per_game": "assists_per_game",
            "field_goal_pct": "career_field_goal_pct",
            "three_point_pct": "career_three_point_pct",
            "free_throw_pct": "career_free_throw_pct",
            "true_shooting_pct": "career_true_shooting_pct",
        },
        mart="nba_player_career_stats",
        mart_where="TRUE",
        game_types=["Regular Season", "Playoffs"],
    ),
    Case(
        name="player seasons from player games",
        view="player_game",
        keys=["person_id", "season_start_year", "game_type"],
        columns={
            "count": "games_played",
            "sum_points": "total_points",
            "sum_rebounds": "total_rebounds",
            "sum_assists": "total_assists",
            "sum_steals": "total_steals",
            "sum_blocks": "total_blocks",
            "sum_turnovers": "total_turnovers",
            "sum_field_goals_made": "total_field_goals_made",
            "sum_field_goals_attempted": "total_field_goals_attempted",
            "sum_three_pointers_made": "total_three_pointers_made",
            "sum_three_pointers_attempted": "total_three_pointers_attempted",
            "sum_free_throws_made": "total_free_throws_made",
            "sum_free_throws_attempted": "total_free_throws_attempted",
            "points_per_game": "points_per_game",
            "rebounds_per_game": "rebounds_per_game",
            "assists_per_game": "assists_per_game",
            "field_goal_pct": "field_goal_pct",
            "three_point_pct": "three_point_pct",
            "free_throw_pct": "free_throw_pct",
        },
        mart="nba_player_season_stats",
        mart_where=MART_SCOPE,
    ),
    Case(
        name="player advanced seasons from player games",
        view="player_game",
        keys=["person_id", "season_start_year", "game_type"],
        columns={
            "count": "games_played",
            "sum_minutes": "total_minutes",
            "true_shooting_pct": "true_shooting_pct",
            "effective_field_goal_pct": "effective_field_goal_pct",
            "usage_pct": "usage_pct",
            "turnover_pct": "turnover_pct",
            "assist_pct": "assist_pct",
            "offensive_rebound_pct": "offensive_rebound_pct",
            "defensive_rebound_pct": "defensive_rebound_pct",
            "rebound_pct": "rebound_pct",
            "steal_pct": "steal_pct",
            "block_pct": "block_pct",
            "sum_player_possessions": "player_possessions",
            "points_per_100": "points_per_100",
            "rebounds_per_100": "rebounds_total_per_100",
            "assists_per_100": "assists_per_100",
            "steals_per_100": "steals_per_100",
            "blocks_per_100": "blocks_per_100",
            "turnovers_per_100": "turnovers_per_100",
        },
        mart="nba_player_season_advanced",
        mart_where=MART_SCOPE,
    ),
    Case(
        name="team seasons from team games",
        view="team_game",
        keys=["team_id", "season_start_year", "game_type"],
        columns={
            "count": "games_played",
            "wins": "wins",
            "losses": "losses",
            "sum_possessions": "possessions",
            "offensive_rating": "offensive_rating",
            "defensive_rating": "defensive_rating",
            "net_rating": "net_rating",
            "pace": "pace",
            "effective_field_goal_pct": "effective_field_goal_pct",
            "true_shooting_pct": "true_shooting_pct",
            "assist_pct": "assist_pct",
            "turnover_pct": "turnover_pct",
            "three_point_attempt_rate": "three_point_attempt_rate",
            "offensive_rebound_pct": "offensive_rebound_pct",
            "free_throw_rate": "free_throw_rate",
            "opp_effective_field_goal_pct": "opp_effective_field_goal_pct",
            "opp_turnover_pct": "opp_turnover_pct",
            "defensive_rebound_pct": "defensive_rebound_pct",
            "opp_free_throw_rate": "opp_free_throw_rate",
        },
        mart="nba_team_advanced_profile",
        mart_where=MART_SCOPE,
    ),
    Case(
        name="team regular seasons from team games",
        view="team_game",
        keys=["team_id", "season_start_year"],
        columns={
            "count": "games_played",
            "wins": "wins",
            "losses": "losses",
            "win_pct": "win_pct",
            "sum_points": "total_points_for",
            "sum_opp_points": "total_points_against",
            "points_per_game": "points_for_per_game",
            "opp_points_per_game": "points_against_per_game",
            "point_margin_per_game": "point_margin_per_game",
        },
        mart="nba_team_season_summary",
        mart_where=f"season_start_year >= {FIRST_SEASON}",
        game_types=["Regular Season"],
    ),
    Case(
        name="league seasons from team games",
        view="team_game",
        keys=["season_start_year", "game_type"],
        # lg_possessions is left out: the mart reports it only for seasons where
        # every team game had a full box, while sum_possessions adds what exists.
        columns={
            "count": "team_games",
            "points_per_game": "lg_points_per_game",
            "pace": "lg_pace",
            "offensive_rating": "lg_offensive_rating",
            "true_shooting_pct": "lg_true_shooting_pct",
            "effective_field_goal_pct": "lg_effective_field_goal_pct",
            "three_point_attempt_rate": "lg_three_point_attempt_rate",
            "free_throw_rate": "lg_free_throw_rate",
            "turnover_pct": "lg_turnover_pct",
            "offensive_rebound_pct": "lg_offensive_rebound_pct",
        },
        mart="nba_league_season_baselines",
        mart_where=MART_SCOPE,
    ),
]


def _token() -> str:
    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    now = int(time.time())
    signing_input = b64(b'{"alg":"HS256","typ":"JWT"}') + b"." + b64(json.dumps({"iat": now, "exp": now + 300}).encode())
    signature = hmac.new(API_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return (signing_input + b"." + b64(signature)).decode()


def _load(query: dict) -> list[dict]:
    """POST a query to /load, polling while Cube answers 'Continue wait'."""
    body = json.dumps({"query": query}).encode()
    while True:
        request = urllib.request.Request(f"{API_URL}/load", data=body, method="POST", headers={
            "Authorization": _token(), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            sys.exit(f"Cube returned {exc.code}: {exc.read().decode()[:500]}")
        except urllib.error.URLError as exc:
            sys.exit(f"Cube is not reachable at {API_URL} ({exc.reason}) -- is `task cube:dev` running?")
        if result.get("error") == "Continue wait":
            continue
        return result["data"]


def cube_rows(case: Case) -> dict[tuple, dict]:
    members = lambda names: [f"{case.view}.{name}" for name in names]  # noqa: E731
    query = {
        "dimensions": members(case.keys),
        "measures": members(case.columns),
        "filters": [{"member": f"{case.view}.game_type", "operator": "equals", "values": case.game_types}],
        "order": [[member, "asc"] for member in members(case.keys)],
        "limit": PAGE_SIZE,
    }
    rows, offset = [], 0
    while True:
        page = _load({**query, "offset": offset})
        rows += page
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return {
        tuple(str(row[f"{case.view}.{key}"]) for key in case.keys):
            {name: row[f"{case.view}.{name}"] for name in case.columns}
        for row in rows
    }


def mart_rows(conn, case: Case) -> dict[tuple, dict]:
    game_type_filter = ""
    if "game_type" in case.keys:
        game_type_filter = f" AND game_type IN ({', '.join(repr(t) for t in case.game_types)})"
    columns = list(case.columns.values())
    sql = (f"SELECT {', '.join(case.keys)}, {', '.join(columns)} FROM marts.{case.mart}"
           f" WHERE {case.mart_where}{game_type_filter}")
    rows = {}
    for record in conn.sql(sql).fetchall():
        key = tuple(str(value) for value in record[:len(case.keys)])
        rows[key] = dict(zip(case.columns, record[len(case.keys):]))
    return rows


def _differs(cube_value, mart_value) -> bool:
    if cube_value is None or mart_value is None:
        return (cube_value is None) != (mart_value is None)
    return not math.isclose(float(cube_value), float(mart_value), rel_tol=REL_TOL, abs_tol=ABS_TOL)


def reconcile(conn, case: Case) -> bool:
    cube, mart = cube_rows(case), mart_rows(conn, case)
    only_cube, only_mart = cube.keys() - mart.keys(), mart.keys() - cube.keys()
    shared = cube.keys() & mart.keys()
    failures = {}
    for name in case.columns:
        bad = [key for key in shared if _differs(cube[key][name], mart[key][name])]
        if bad:
            failures[name] = bad
    ok = not (only_cube or only_mart or failures)
    print(f"{'ok  ' if ok else 'FAIL'} {case.name}: {case.view} vs {case.mart}, "
          f"{len(shared):,} rows x {len(case.columns)} values")
    for label, keys in (("only in Cube", only_cube), ("only in the mart", only_mart)):
        if keys:
            print(f"       {len(keys):,} rows {label}, e.g. {sorted(keys)[:3]}")
    for name, keys in failures.items():
        key = keys[0]
        print(f"       {name} vs {case.columns[name]}: {len(keys):,} rows differ, "
              f"e.g. {key}: Cube {cube[key][name]}, mart {mart[key][name]}")
    return ok


def main() -> None:
    if not API_SECRET:
        sys.exit("CUBEJS_API_SECRET is not set (expected in cube/.env).")
    conn = connect_lake(read_only=True)
    results = [reconcile(conn, case) for case in CASES]
    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
