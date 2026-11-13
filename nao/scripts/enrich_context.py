"""Add the lake's dbt descriptions and column names to nao's context.

Runs after `nao sync` (the nao:sync task does both, after `dbt parse`). Four jobs:

1. Fill in descriptions in nao's generated columns.md files. dbt writes model
   and column descriptions into the lake as comments (persist_docs on the
   marts), and nao's columns.md template shows them, but nao-core 0.3.31's
   DuckLake context looks them up with the catalog-qualified schema name
   (schema_name = 'lake.marts'), which matches nothing, so every file says
   "_No description available._". This writes them in nao's own format, so it
   stops changing anything once nao fixes the lookup.

2. Rewrite the generated section at the end of nao/RULES.md: the column names
   of every synced table. RULES.md is part of the model's prompt on every turn,
   so the model has the real names without having to read columns.md first,
   which the local model often skips (it guessed `total_three_pointers` for
   `total_three_pointers_made`).

3. Write nao/docs/nba/nba_marts.md, the per-table summary (grain, description,
   coverage), from dbt's manifest. It used to be written by hand and drifted
   from dbt (it gave the wrong table prefix and called ratings fractions).

4. Rewrite the Cube section of RULES.md: every published view with its
   description and member names, from Cube's /meta, plus the current and last
   completed season. nao answers metric questions through the Cube MCP server
   (ADR 0005), and the model writes a query from these names without calling
   describe_model on the whole model, which is too long for its context. Needs
   `task cube:dev`; without it the previous Cube section is kept, with a warning.

Reads the lake READ_ONLY through data-ingestion/lake.py, so LAKE_DATA_PATH must
be set (the Taskfile exports it).

Usage:
  python nao/scripts/enrich_context.py
"""

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data-ingestion"))

from lake import connect_lake  # noqa: E402

CONTEXT_DIR = ROOT / "nao" / "databases" / "type=ducklake" / "database=lake"
RULES = ROOT / "nao" / "RULES.md"
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
MARTS_DOC = ROOT / "nao" / "docs" / "nba" / "nba_marts.md"
RULES_HEADING = "## Columns by table (generated)"
CUBE_HEADING = "## Cube views (generated)"
_cube_config = {**dotenv_values(ROOT / "cube" / ".env"), **os.environ}
CUBE_API_URL = _cube_config.get("CUBE_API_URL", "http://localhost:4000/cubejs-api/v1").rstrip("/")
CUBE_API_SECRET = _cube_config.get("CUBEJS_API_SECRET")
NO_DESCRIPTION = "_No description available._"
# A column line nao wrote without a description: "- name (type)".
BARE_COLUMN_LINE = re.compile(r"^- (\w+) \(([^)]*)\)$")
MAX_DESCRIPTION = 256  # nao's template truncates descriptions to this


def normalise(text: str | None) -> str:
    return " ".join(str(text or "").split())


def truncate_middle(text: str, limit: int = MAX_DESCRIPTION) -> str:
    """Match nao's truncate_middle filter, so descriptions look like nao's own."""
    if len(text) <= limit:
        return text
    keep = (limit - 3) // 2
    return f"{text[:keep]}...{text[-keep:]}"


def synced_tables() -> list[tuple[str, str, Path]]:
    """(schema, table, columns.md path) for every table nao synced, e.g. ('marts', 'nba_team_dim', ...)."""
    tables = []
    for path in sorted(CONTEXT_DIR.glob("schema=*/table=*/columns.md")):
        schema = path.parent.parent.name.removeprefix("schema=").removeprefix("lake.")
        table = path.parent.name.removeprefix("table=")
        tables.append((schema, table, path))
    return tables


def fetch_comments(conn, schema: str, table: str) -> tuple[str, list[tuple[str, str]]]:
    """The table's comment and its (column, comment) pairs in column order."""
    table_comment = conn.execute(
        "select comment from duckdb_tables() "
        "where database_name = 'lake' and schema_name = ? and table_name = ?",
        [schema, table],
    ).fetchone()
    columns = conn.execute(
        "select column_name, comment from duckdb_columns() "
        "where database_name = 'lake' and schema_name = ? and table_name = ? "
        "order by column_index",
        [schema, table],
    ).fetchall()
    return normalise(table_comment[0] if table_comment else None), [
        (name, normalise(comment)) for name, comment in columns
    ]


def enrich_columns_md(path: Path, table_comment: str, column_comments: dict[str, str]) -> bool:
    """Write descriptions into one columns.md. Returns True if the file changed."""
    text = path.read_text()
    lines = []
    for line in text.split("\n"):
        if line == NO_DESCRIPTION and table_comment:
            line = table_comment
        elif match := BARE_COLUMN_LINE.match(line):
            name, column_type = match.groups()
            if description := column_comments.get(name):
                line = f'- {name} ({column_type}, "{truncate_middle(description)}")'
        lines.append(line)
    new_text = "\n".join(lines)
    if new_text == text:
        return False
    path.write_text(new_text)
    return True


def rules_section(columns_by_table: dict[str, list[str]]) -> str:
    lines = [
        RULES_HEADING,
        "",
        "Written by `task nao:sync` from the lake; don't edit by hand. These are the",
        "exact column names: use them as written, and read the table's `columns.md`",
        "for what a column means.",
        "",
    ]
    for table, columns in columns_by_table.items():
        lines.append(f"- `lake.marts.{table}`: {', '.join(columns)}")
    return "\n".join(lines) + "\n"


def _cube_token() -> str:
    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    now = int(time.time())
    signing_input = b64(b'{"alg":"HS256","typ":"JWT"}') + b"." + b64(json.dumps({"iat": now, "exp": now + 300}).encode())
    signature = hmac.new(CUBE_API_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return (signing_input + b"." + b64(signature)).decode()


def fetch_cube_meta() -> dict | None:
    """Cube's /meta, or None (with a warning) when Cube isn't running or configured."""
    if not CUBE_API_SECRET:
        print("Warning: CUBEJS_API_SECRET is not set (cube/.env); keeping the previous Cube section.")
        return None
    request = urllib.request.Request(f"{CUBE_API_URL}/meta", headers={"Authorization": _cube_token()})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Warning: Cube is not reachable at {CUBE_API_URL} ({exc}); keeping the previous "
              "Cube section. Start `task cube:dev` and re-run `task nao:sync` to refresh it.")
        return None


def fetch_seasons(conn) -> tuple[str | None, tuple[str, int] | None]:
    """The current season's label and the last completed season's (label, start year)."""
    current = conn.execute("select season_label from marts.nba_seasons_dim where is_current").fetchone()
    completed = conn.execute(
        "select season_label, season_start_year from marts.nba_seasons_dim "
        "where coverage_tier = 'complete' order by season_start_year desc limit 1"
    ).fetchone()
    return (current[0] if current else None), completed


def cube_section(meta: dict, current: str | None, completed: tuple[str, int] | None) -> str:
    lines = [
        CUBE_HEADING,
        "",
        "Written by `task nao:sync` from Cube's `/meta`; don't edit by hand. These are the",
        "published views and their exact member names: write each as `<view>.<member>`.",
        "",
    ]
    if completed:
        label, start_year = completed
        in_progress = f"{current} is the season in progress; " if current else ""
        lines += [f"Seasons as of the last sync: {in_progress}the last completed season is {label} "
                  f"(`season_start_year` {start_year}).", ""]
    for view in meta["cubes"]:
        if view.get("type") != "view" or not view.get("public", True):
            continue
        name = view["name"]

        def members(kind: str) -> str:
            return ", ".join(m["name"].removeprefix(f"{name}.") for m in view.get(kind, [])
                             if m.get("public", True))

        lines += [f"### {name}", "", normalise(view.get("description")), ""]
        lines.append(f"- Measures: {members('measures')}")
        lines.append(f"- Dimensions: {members('dimensions')}")
        if segments := members("segments"):
            lines.append(f"- Segments: {segments}")
        lines.append("")
    return "\n".join(lines)


def write_rules(columns_by_table: dict[str, list[str]], cube_text: str | None) -> None:
    """Rewrite the generated sections at the end of RULES.md, keeping the hand-written part."""
    text = RULES.read_text()
    first_generated = min(text.index(h) for h in (CUBE_HEADING, RULES_HEADING) if h in text)
    hand_written = text[:first_generated].rstrip("\n")
    if cube_text is None and CUBE_HEADING in text:
        cube_text = text[text.index(CUBE_HEADING):text.index(RULES_HEADING)].rstrip("\n") + "\n"
    cube_part = f"{cube_text}\n" if cube_text else ""
    RULES.write_text(f"{hand_written}\n\n{cube_part}{rules_section(columns_by_table)}")


def write_marts_doc(tables: list[str]) -> None:
    """Write nba_marts.md from each synced mart's dbt description and meta."""
    if not MANIFEST.exists():
        sys.exit(f"{MANIFEST} not found: run `dbt parse` first (task nao:sync does).")
    models = {n["name"]: n for n in json.loads(MANIFEST.read_text())["nodes"].values()
              if n["resource_type"] == "model" and n["schema"] == "marts"}
    lines = [
        "# NBA marts",
        "",
        "Generated by `task nao:sync` from the dbt models (dbt/models/marts/nba/marts_nba.yml);",
        "don't edit by hand. Query tables as `lake.marts.<table>`; RULES.md has the default",
        "scope and which table answers which question.",
        "",
    ]
    for table in tables:
        model = models.get(table)
        if not model:
            continue
        meta = model.get("config", {}).get("meta") or model.get("meta") or {}
        lines += [f"## {table}", ""]
        if meta.get("grain"):
            lines += [f"**Grain:** {meta['grain']}.", ""]
        lines += [normalise(model.get("description")), ""]
        if meta.get("seasonality"):
            lines += [f"**Coverage:** {normalise(meta['seasonality'])}", ""]
        if meta.get("additive") is True:
            lines += ["**Additive:** yes. Sum the counts and components across rows and recompute "
                      "rates from them; never sum or average a rate column.", ""]
        elif meta.get("additive") is False:
            columns = ", ".join(meta.get("non_additive_columns") or [])
            lines += [f"**Additive:** no. Never sum or average {columns} across rows: read them "
                      "one row at a time, or get the rate over several rows from Cube.", ""]
    MARTS_DOC.write_text("\n".join(lines))


def main() -> None:
    tables = synced_tables()
    if not tables:
        sys.exit(f"No synced tables under {CONTEXT_DIR}: run `nao sync` first.")

    conn = connect_lake(read_only=True)
    columns_by_table = {}
    changed = 0
    for schema, table, path in tables:
        table_comment, columns = fetch_comments(conn, schema, table)
        changed += enrich_columns_md(path, table_comment, dict(columns))
        columns_by_table[table] = [name for name, _ in columns]

    meta = fetch_cube_meta()
    cube_text = cube_section(meta, *fetch_seasons(conn)) if meta else None
    write_rules(columns_by_table, cube_text)
    write_marts_doc(list(columns_by_table))
    views = "kept the previous Cube views" if meta is None else "refreshed the Cube views"
    print(f"Descriptions added to {changed} of {len(tables)} columns.md files; "
          f"RULES.md lists the columns of {len(columns_by_table)} tables and {views}.")


if __name__ == "__main__":
    main()
