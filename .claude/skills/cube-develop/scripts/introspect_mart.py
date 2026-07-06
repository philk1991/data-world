#!/usr/bin/env python3
"""Introspect a dbt mart for the cube-develop skill.

Run from the project root:

    source .venv/bin/activate
    python .claude/skills/cube-develop/scripts/introspect_mart.py --list
    python .claude/skills/cube-develop/scripts/introspect_mart.py <mart_name>

`--list` enumerates every mart model in the manifest and flags which ones
already have a cube/model/cubes/<name>.yml, so the skill can offer the user
a menu of marts that don't have a cube yet.

Given a mart name, prints one JSON object with:
- the model's dbt description, meta (grain/purpose/business_question/
  seasonality/relationships) and per-column descriptions, read from
  dbt/target/manifest.json
- the table's actual live columns and DuckDB types via DESCRIBE against
  data/spotify.duckdb (read-only), each mapped to a suggested Cube type
- warnings where the manifest and the live table disagree (a documented
  column that no longer exists, or a live column with no dbt description)

The live DESCRIBE is the source of truth for types — manifest column
metadata doesn't reliably carry a data_type, so types are never guessed
from column names alone.
"""
import json
import re
import sys
from pathlib import Path

import duckdb

MANIFEST_PATH = Path("dbt/target/manifest.json")
DUCKDB_PATH = "data/spotify.duckdb"
CUBES_DIR = Path("cube/model/cubes")


def map_duckdb_type(duckdb_type: str) -> str:
    t = duckdb_type.upper()
    if any(k in t for k in ("TIMESTAMP", "DATE", "TIME")):
        return "time"
    if "BOOL" in t:
        return "boolean"
    if any(k in t for k in (
        "INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "HUGEINT", "REAL",
    )):
        return "number"
    return "string"


def find_cube_file_for_mart(mart_name):
    """Find the cube yml (if any) whose sql_table references this mart.

    Cube file/cube names are NOT always identical to the mart name — e.g.
    cube/model/cubes/spotify_top_artists.yml has sql_table: marts.top_artists_by_period.
    So existence must be checked via sql_table, never via filename == mart_name.
    """
    if not CUBES_DIR.exists():
        return None
    pattern = re.compile(r"sql_table:\s*marts\.(\w+)")
    for path in CUBES_DIR.glob("*.yml"):
        match = pattern.search(path.read_text())
        if match and match.group(1) == mart_name:
            return path
    return None


def load_manifest():
    if not MANIFEST_PATH.exists():
        print(json.dumps({
            "error": "manifest.json not found — run `task dbt:compile` "
                     "(or `dbt compile` from dbt/) first",
        }))
        raise SystemExit(1)
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def mart_nodes(manifest):
    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") == "model" and "marts" in node.get("original_file_path", ""):
            yield uid, node


def list_marts(manifest):
    marts = []
    for _, node in mart_nodes(manifest):
        path_parts = Path(node["original_file_path"]).parts
        domain = path_parts[2] if len(path_parts) > 2 else None
        existing_cube = find_cube_file_for_mart(node["name"])
        marts.append({
            "name": node["name"],
            "domain": domain,
            "description": (node.get("description") or "").strip(),
            "has_cube": existing_cube is not None,
            "cube_file": existing_cube.name if existing_cube else None,
        })
    marts.sort(key=lambda m: (m["domain"] or "", m["name"]))
    print(json.dumps(marts, indent=2))


def introspect(manifest, mart_name):
    target = None
    for _, node in mart_nodes(manifest):
        if node["name"] == mart_name:
            target = node
            break

    if target is None:
        print(json.dumps({"error": f"No mart model named '{mart_name}' found in manifest"}))
        raise SystemExit(1)

    dbt_columns = {
        name: col.get("description", "").strip()
        for name, col in target.get("columns", {}).items()
    }

    conn = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        rows = conn.execute(f'DESCRIBE "marts"."{mart_name}"').fetchall()
    except Exception as e:
        print(json.dumps({"error": f"Could not DESCRIBE marts.{mart_name}: {e}"}))
        raise SystemExit(1)

    duckdb_columns = [
        {"name": r[0], "duckdb_type": r[1], "cube_type": map_duckdb_type(r[1])}
        for r in rows
    ]
    live_names = {c["name"] for c in duckdb_columns}
    doc_names = set(dbt_columns.keys())

    warnings = []
    for name in doc_names - live_names:
        warnings.append(f"Column '{name}' is documented in dbt but not present in the live table")
    for name in live_names - doc_names:
        warnings.append(f"Column '{name}' exists in the live table but has no dbt description")

    existing_cube = find_cube_file_for_mart(mart_name)

    print(json.dumps({
        "mart_name": mart_name,
        "cube_file_exists": existing_cube is not None,
        "existing_cube_file": str(existing_cube) if existing_cube else None,
        "suggested_cube_file_if_new": str(CUBES_DIR / f"{mart_name}.yml"),
        "note": (
            "suggested_cube_file_if_new assumes the cube name equals the mart "
            "name. Check references/conventions.md's naming rule first — marts "
            "not already domain-prefixed (unlike nba_*/sb_*) get a domain-"
            "prefixed cube name instead, e.g. ohlcv_1h -> crypto_ohlcv_1h.yml."
        ),
        "dbt": {
            "description": (target.get("description") or "").strip(),
            "meta": target.get("meta", {}),
            "columns": dbt_columns,
        },
        "duckdb_columns": duckdb_columns,
        "warnings": warnings,
    }, indent=2, default=str))


if __name__ == "__main__":
    manifest = load_manifest()
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: introspect_mart.py --list | <mart_name>"}))
        raise SystemExit(1)
    if sys.argv[1] == "--list":
        list_marts(manifest)
    else:
        introspect(manifest, sys.argv[1])
