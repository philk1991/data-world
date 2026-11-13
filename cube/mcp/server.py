"""Local MCP server over the Cube REST API.

Lets an MCP client (Claude Code, Claude Desktop) answer natural-language questions
from the Cube semantic layer: it reads the model through /meta and runs queries
through /load. Runs over stdio — the client starts it as a child process and the
only network traffic is to the Cube dev server on localhost, so nothing is exposed.

Config, read from cube/.env (the same file the Cube dev server uses):
  CUBEJS_API_SECRET  signs a short-lived JWT for each request (required)
  CUBE_API_URL       defaults to http://localhost:4000/cubejs-api/v1
"""

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

CUBE_DIR = Path(__file__).resolve().parent.parent
_config = {**dotenv_values(CUBE_DIR / ".env"), **os.environ}

API_URL = _config.get("CUBE_API_URL", "http://localhost:4000/cubejs-api/v1").rstrip("/")
API_SECRET = _config.get("CUBEJS_API_SECRET")

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
# Cube answers a slow query with {"error": "Continue wait"} and expects the client to poll.
CONTINUE_WAIT_TIMEOUT_S = 60

INSTRUCTIONS = """\
Answers questions from the Cube semantic layer over the data-world lake (NBA and
Spotify marts). Work in this order:
1. Call describe_model once to see the views (NBA: player_game, player_season,
   player_career, team_game, team_season, league_season, game, player, shot)
   and cubes, with their measures and dimensions. Read the descriptions: they
   state the grain, the default scope (player views default to the Regular
   Season until you filter game_type) and when stats were not recorded.
2. Build a query from one view's member names and call query. Prefer the model's
   own measures (e.g. points_per_game, win_pct, true_shooting_pct) over computing
   ratios or averaging rows yourself — they are weighted correctly across rows.
3. Query one view at a time; outside the views, only combine members from cubes
   that share a join_group.
4. There are no rank members. For "where did X rank", query the whole
   leaderboard (the measure and the player or team name, the season filter and
   the qualifying segment, ordered by the measure, limit 1000) and read X's
   `row` number; filtering on X first would rank X against itself.
5. When answering, state the filters you applied (season, game type) and any
   data-coverage caveat from the descriptions. Values come back unrounded:
   display them at the member's format (a d3 specifier: ".3f" for rates such as
   true shooting, ".1f" for per-game stats and ratings).
"""

UNKNOWN_MEMBER_HINT = (
    " -- use only the members describe_model lists for that view. There are no rank members:"
    " to rank, order a leaderboard query by the measure and read the row number."
)

QUERY_FORMAT = """\
A Cube REST query (JSON object). Members are always "<cube>.<member>". Keys:
  measures: ["team_season.win_pct", ...]
  dimensions: ["team_season.team_full_name", ...]
  filters: [{"member": "<cube>.<member>", "operator": "<op>", "values": ["..."]}]
    operators: equals, notEquals, contains, notContains, startsWith, endsWith,
    gt, gte, lt, lte, set, notSet, inDateRange, notInDateRange, beforeDate, afterDate.
    values are always strings, also for numbers ("2023"); equals with several
    values matches any of them. For OR/AND use
    {"or": [filter, ...]} / {"and": [filter, ...]}. Filtering on a measure
    filters after aggregation (like HAVING).
  segments: ["player_season.qualified"] — named, predefined filters
    listed by describe_model. Prefer a segment over rebuilding its filter by hand.
  timeDimensions: [{"dimension": "<cube>.<time dim>", "granularity": "year",
    "dateRange": ["2020-01-01", "2020-12-31"]}] — only for type-time dimensions.
  order: {"<cube>.<member>": "desc"} (or a list of [member, "asc"|"desc"] pairs)
  limit: integer (default 100, max 1000); offset: integer
Returns {"row_count", "limit", "columns", "rows"}: one array per row in the
columns' order, led by its 1-based row number, so a row's number in an ordered
query is its position on the leaderboard.
Example — best regular-season records of 2023-24:
  {"measures": ["team_season.win_pct"],
   "dimensions": ["team_season.team_full_name"],
   "filters": [{"member": "team_season.season_label",
                "operator": "equals", "values": ["2023-24"]}],
   "order": {"team_season.win_pct": "desc"}, "limit": 5}
"""

server = MCPServer(name="cube", instructions=INSTRUCTIONS)


def _token() -> str:
    if not API_SECRET:
        raise ToolError(f"CUBEJS_API_SECRET is not set (expected in {CUBE_DIR / '.env'}).")
    return jwt.encode({"iat": int(time.time()), "exp": int(time.time()) + 300}, API_SECRET, algorithm="HS256")


async def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """Call the Cube REST API, polling while Cube reports 'Continue wait'."""
    deadline = time.monotonic() + CONTINUE_WAIT_TIMEOUT_S
    async with httpx.AsyncClient(base_url=API_URL, timeout=30) as client:
        while True:
            try:
                response = await client.request(method, path, headers={"Authorization": _token()}, **kwargs)
            except httpx.ConnectError as exc:
                raise ToolError(f"Cube is not reachable at {API_URL} — is `task cube:dev` running?") from exc
            body = response.json()
            if body.get("error") == "Continue wait" and time.monotonic() < deadline:
                continue
            if response.status_code >= 400 or "error" in body:
                error = body.get("error", body)
                hint = UNKNOWN_MEMBER_HINT if "not found for path" in str(error) else ""
                raise ToolError(f"Cube returned an error: {error}{hint}")
            return body


def _member(member: dict[str, Any]) -> dict[str, Any]:
    entry = {"name": member["name"]}
    if member.get("type"):  # segments have no type
        entry["type"] = member["type"]
    if member.get("description"):
        entry["description"] = member["description"]
    fmt = member.get("format")  # e.g. {"type": "custom-numeric", "value": ".3f"}
    if fmt:
        entry["format"] = fmt.get("value", fmt) if isinstance(fmt, dict) else fmt
    return entry


@server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
async def describe_model(cube: str | None = None) -> str:
    """List the cubes in the semantic layer with their measures and dimensions.

    Call this before writing a query. Each cube's description states its grain
    (what one row is). Members can only be combined in one query when their cubes
    share a join_group. Pass `cube` to describe a single cube.
    """
    meta = await _request("GET", "/meta")
    cubes = []
    for c in meta["cubes"]:
        if (cube and c["name"] != cube) or not c.get("public", True):
            continue
        cubes.append({
            "name": c["name"],
            "type": c.get("type", "cube"),
            "description": c.get("description"),
            "join_group": c.get("connectedComponent"),
            "measures": [_member(m) for m in c["measures"] if m.get("public", True)],
            "dimensions": [_member(d) for d in c["dimensions"] if d.get("public", True)],
            "segments": [_member(s) for s in c.get("segments", []) if s.get("public", True)],
        })
    if cube and not cubes:
        raise ToolError(f"No cube named {cube!r}. Call describe_model without arguments to list them.")
    return json.dumps(cubes, indent=1)


@server.tool(description=f"Run a query against the Cube semantic layer and return the rows.\n\n{QUERY_FORMAT}",
             annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
async def query(query: dict[str, Any]) -> str:
    query = {**query, "limit": min(int(query.get("limit", DEFAULT_LIMIT)), MAX_LIMIT)}
    body = await _request("POST", "/load", json={"query": query})
    rows = body.get("data", [])
    # Arrays rather than objects: repeating every member name on every row tripled
    # the size of a leaderboard, which a local model's context can't spare.
    columns = list(rows[0]) if rows else [*query.get("dimensions", []), *query.get("measures", [])]
    header = json.dumps({"row_count": len(rows), "limit": query["limit"], "columns": ["row", *columns]})
    lines = [json.dumps([number, *(row.get(c) for c in columns)], default=str)
             for number, row in enumerate(rows, start=1)]
    return header[:-1] + ', "rows": [\n' + ",\n".join(lines) + "\n]}"


@server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
async def generated_sql(query: dict[str, Any]) -> str:
    """Show the SQL Cube generates for a query, without running it.

    Takes the same query object as the `query` tool. Useful for checking how a
    measure is computed or which joins Cube chose.
    """
    body = await _request("POST", "/sql", json={"query": query})
    sql, params = body["sql"]["sql"]
    return json.dumps({"sql": sql, "params": params}, indent=1, default=str)


if __name__ == "__main__":
    server.run()
