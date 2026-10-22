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
1. Call describe_model once to see the cubes, their measures and dimensions. Read
   the descriptions: they state each cube's grain and when stats were not recorded.
2. Build a Cube query from those member names and call query. Prefer the model's
   own measures (e.g. points_per_game, win_pct, true_shooting_pct) over computing
   ratios or averaging rows yourself — they are weighted correctly across rows.
3. Only combine members from cubes that share a join_group.
4. When answering, state the filters you applied (season, game type) and any
   data-coverage caveat from the descriptions.
"""

QUERY_FORMAT = """\
A Cube REST query (JSON object). Members are always "<cube>.<member>". Keys:
  measures: ["nba_team_season_summary.win_pct", ...]
  dimensions: ["nba_team_dim.current_full_name", ...]
  filters: [{"member": "<cube>.<member>", "operator": "<op>", "values": ["..."]}]
    operators: equals, notEquals, contains, notContains, startsWith, endsWith,
    gt, gte, lt, lte, set, notSet, inDateRange, notInDateRange, beforeDate, afterDate.
    values are always strings, also for numbers ("2023"). For OR/AND use
    {"or": [filter, ...]} / {"and": [filter, ...]}. Filtering on a measure
    filters after aggregation (like HAVING).
  segments: ["nba_player_season_stats.qualified"] — named, predefined filters
    listed by describe_model. Prefer a segment over rebuilding its filter by hand.
  timeDimensions: [{"dimension": "<cube>.<time dim>", "granularity": "year",
    "dateRange": ["2020-01-01", "2020-12-31"]}] — only for type-time dimensions.
  order: {"<cube>.<member>": "desc"} (or a list of [member, "asc"|"desc"] pairs)
  limit: integer (default 100, max 1000); offset: integer
Example — best regular-season records of 2023-24:
  {"measures": ["nba_team_season_summary.win_pct"],
   "dimensions": ["nba_team_dim.current_full_name"],
   "filters": [{"member": "nba_team_season_summary.season_label",
                "operator": "equals", "values": ["2023-24"]}],
   "order": {"nba_team_season_summary.win_pct": "desc"}, "limit": 5}
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
                raise ToolError(f"Cube returned an error: {body.get('error', body)}")
            return body


def _member(member: dict[str, Any]) -> dict[str, Any]:
    entry = {"name": member["name"]}
    if member.get("type"):  # segments have no type
        entry["type"] = member["type"]
    if member.get("description"):
        entry["description"] = member["description"]
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
    return json.dumps({"row_count": len(rows), "limit": query["limit"], "rows": rows}, indent=1, default=str)


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
