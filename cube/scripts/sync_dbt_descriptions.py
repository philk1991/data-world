"""Copy dbt column descriptions onto the Cube dimensions that expose them.

A cube built on a dbt mart (sql_table: marts.<model>) usually has dimensions
that are the mart's columns as-is (sql: season_start_year). Their description
should be the dbt column's description — after doc blocks are rendered — so
Claude (via the Cube MCP server), the Playground and the dbt docs all say the
same thing. dbt is the source of truth; this script writes it into the cube
YAML so the description stays visible where the cube is defined.

Synced: dimensions whose sql is a bare column name of the cube's mart.
Left alone: computed dimensions (sql is an expression, e.g. player_name) and
all measures, which are Cube definitions with no dbt column behind them.

Reads dbt/target/manifest.json, so run `dbt parse` first (the Task targets do).

Usage:
  python cube/scripts/sync_dbt_descriptions.py           # rewrite cube YAML
  python cube/scripts/sync_dbt_descriptions.py --check   # exit 1 on drift
"""

import json
import re
import sys
import textwrap
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
CUBES_DIR = ROOT / "cube" / "model" / "cubes"

BARE_COLUMN = re.compile(r"\w+")
INDENT = " " * 8  # dimension keys sit at 8 spaces in the cube files
WIDTH = 80


def normalise(text: str) -> str:
    return " ".join(str(text or "").split())


def render(description: str) -> list[str]:
    """YAML lines for `description:` — one plain line when it is safe, else folded."""
    line = f"{INDENT}description: {description}"
    if len(line) <= WIDTH + 20:
        try:
            if yaml.safe_load(f"k: {description}") == {"k": description}:
                return [line]
        except yaml.YAMLError:
            pass
    body = textwrap.wrap(description, WIDTH - len(INDENT) - 2, break_on_hyphens=False)
    return [f"{INDENT}description: >"] + [f"{INDENT}  {part}" for part in body]


def dimension_span(lines: list[str], cube: str, dimension: str) -> tuple[int, int]:
    """Line range of one dimension entry: from its `- name:` to the next entry or section."""
    cube_at = next(i for i, l in enumerate(lines) if l.strip() == f"- name: {cube}" and l.startswith("  - "))
    dims_at = next(i for i in range(cube_at, len(lines)) if lines[i] == "    dimensions:")
    start = next(i for i in range(dims_at, len(lines)) if lines[i] == f"      - name: {dimension}")
    end = start + 1
    while end < len(lines) and lines[end].startswith(INDENT):
        end += 1
    return start, end


def set_description(lines: list[str], start: int, end: int, description: str) -> list[str]:
    """Replace (or add) the description key inside one dimension entry."""
    entry = lines[start:end]
    at = next((i for i, l in enumerate(entry) if l.startswith(f"{INDENT}description:")), None)
    if at is None:
        new_entry = entry + render(description)
    else:
        stop = at + 1
        if entry[at].rstrip().endswith((">", ">-", "|", "|-")):
            while stop < len(entry) and entry[stop].startswith(INDENT + "  "):
                stop += 1
        new_entry = entry[:at] + render(description) + entry[stop:]
    return lines[:start] + new_entry + lines[end:]


def main() -> int:
    check = "--check" in sys.argv[1:]
    if not MANIFEST.exists():
        print(f"{MANIFEST} not found — run `dbt parse` first.")
        return 1
    manifest = json.loads(MANIFEST.read_text())
    marts = {n["name"]: n for n in manifest["nodes"].values()
             if n["resource_type"] == "model" and n["schema"] == "marts"}

    drift, missing = [], []
    for path in sorted(CUBES_DIR.glob("*.yml")):
        text = path.read_text()
        lines = text.split("\n")
        for cube in yaml.safe_load(text).get("cubes", []):
            mart = marts.get(str(cube.get("sql_table", "")).split(".")[-1])
            if not mart:
                continue
            for dim in cube.get("dimensions", []):
                column = str(dim.get("sql", ""))
                if not BARE_COLUMN.fullmatch(column):
                    continue
                wanted = normalise(mart["columns"].get(column, {}).get("description"))
                if not wanted:
                    missing.append(f"{cube['name']}.{dim['name']}: {mart['name']}.{column} has no dbt description")
                    continue
                if normalise(dim.get("description")) == wanted:
                    continue
                drift.append(f"{cube['name']}.{dim['name']} (from {mart['name']}.{column})")
                if not check:
                    start, end = dimension_span(lines, cube["name"], dim["name"])
                    lines = set_description(lines, start, end, wanted)
        new_text = "\n".join(lines)
        if not check and new_text != text:
            yaml.safe_load(new_text)  # never write a file Cube can't parse
            path.write_text(new_text)

    for line in missing:
        print(f"warning: {line}")
    if not drift:
        print("Cube dimension descriptions match dbt.")
        return 0
    verb = "differ from dbt" if check else "updated from dbt"
    print(f"{len(drift)} dimension description(s) {verb}:")
    for line in drift:
        print(f"  - {line}")
    if check:
        print("Run `task cube:docs:sync` to copy them over.")
    return 1 if check else 0


if __name__ == "__main__":
    sys.exit(main())
