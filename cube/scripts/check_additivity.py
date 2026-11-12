"""Check the additivity tags on the dbt marts and that Cube respects them.

ADR 0002's boundary rule: dbt stores additive components and Cube owns the
ratios; a value that can't be rebuilt by a sum over sum stays in dbt, tagged
`meta.additive: false` with the offending columns in `meta.non_additive_columns`,
and Cube may expose it only as a dimension or a weighted measure, never summed or
averaged across rows. Rules:

1. Every mart in a checked domain, other than a `_dim`, declares `meta.additive`
   (true or false). `additive: false` lists `non_additive_columns`, each one a
   documented column of the model; `additive: true` lists none.
2. No Cube measure sums or averages a non-additive column: a `sum`, `avg` or
   `running_total` measure over it, or `SUM(col)` / `AVG(...col...)` in a
   `number` measure. A weighted sum such as SUM(possessions * lg_offensive_rating)
   is allowed. Columns are matched as `{CUBE}.col`, `{col}` and `{cube.col}`.

Reads the dbt and Cube YAML directly, so it needs no dbt parse.
Usage: python cube/scripts/check_additivity.py [domain ...]   (default: nba)
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MARTS_DIR = ROOT / "dbt" / "models" / "marts"
CUBES_DIR = ROOT / "cube" / "model" / "cubes"

AGGREGATING_TYPES = {"sum", "avg", "running_total"}
SQL_TABLE = re.compile(r"\bmarts\.(\w+)")
MEMBER_REF = re.compile(r"\{CUBE\}\.(\w+)|\{(\w+)\}|\{(\w+)\.(\w+)\}")


def load_marts() -> dict[str, tuple[str, dict, set[str]]]:
    """Model name -> (domain, meta, documented columns), for every mart."""
    marts = {}
    for path in sorted(MARTS_DIR.glob("*/*.yml")):
        for model in (yaml.safe_load(path.read_text()) or {}).get("models", []):
            meta = (model.get("config") or {}).get("meta") or {}
            columns = {column["name"] for column in model.get("columns", [])}
            marts[model["name"]] = (path.parent.name, meta, columns)
    return marts


def check_tags(marts: dict, domains: list[str]) -> list[str]:
    errors = []
    for name, (domain, meta, columns) in marts.items():
        if domain not in domains or name.endswith("_dim"):
            continue
        additive, listed = meta.get("additive"), meta.get("non_additive_columns") or []
        if not isinstance(additive, bool):
            errors.append(f"{name}: meta.additive must be true or false")
        elif additive and listed:
            errors.append(f"{name}: additive: true but lists non_additive_columns")
        elif not additive and not listed:
            errors.append(f"{name}: additive: false needs non_additive_columns")
        for column in sorted(set(listed) - columns):
            errors.append(f"{name}: non_additive_columns names {column}, which is not a documented column")
    return errors


def cube_marts(cubes: list[dict]) -> dict[str, str]:
    """Cube name -> the mart it reads (`meta.dbt_model`, else `sql_table`)."""
    mapping = {}
    for cube in cubes:
        mart = (cube.get("meta") or {}).get("dbt_model")
        if not mart:
            match = SQL_TABLE.search(cube.get("sql_table", ""))
            mart = match.group(1) if match else None
        if mart:
            mapping[cube["name"]] = mart
    for cube in cubes:  # an extending cube reads its parent's mart
        if cube.get("extends") and cube["name"] not in mapping:
            parent = cube["extends"].strip("{} ")
            if parent in mapping:
                mapping[cube["name"]] = mapping[parent]
    return mapping


def check_measures(marts: dict) -> list[str]:
    cubes = []
    for path in sorted(CUBES_DIR.glob("*.yml")):
        cubes += (yaml.safe_load(path.read_text()) or {}).get("cubes", [])
    mart_of = cube_marts(cubes)
    non_additive = {
        cube: set(marts[mart][1].get("non_additive_columns") or [])
        for cube, mart in mart_of.items() if mart in marts
    }

    def references(cube: str, sql: str) -> set[str]:
        found = set()
        for own, bare, other_cube, other in MEMBER_REF.findall(sql):
            target, column = (other_cube, other) if other_cube else (cube, own or bare)
            if column in non_additive.get(target, set()):
                found.add(column)
        return found

    errors = []
    for cube in cubes:
        for measure in cube.get("measures", []):
            sql = str(measure.get("sql", ""))
            for column in sorted(references(cube["name"], sql)):
                escaped = re.escape(column)
                direct = re.search(rf"SUM\(\s*\{{(?:CUBE\}}\.|\w+\.)?{escaped}\}}?\s*\)", sql, re.IGNORECASE)
                averaged = re.search(rf"AVG\([^)]*{escaped}", sql, re.IGNORECASE)
                if measure.get("type") in AGGREGATING_TYPES or direct or averaged:
                    errors.append(f"{cube['name']}.{measure['name']}: aggregates {column}, which its mart "
                                  "tags non-additive; expose it as a dimension or weight it")
    return errors


def main() -> None:
    domains = sys.argv[1:] or ["nba"]
    marts = load_marts()
    errors = check_tags(marts, domains) + check_measures(marts)
    for error in errors:
        print(error)
    if errors:
        sys.exit(1)
    tagged = sum(1 for _, meta, _ in marts.values() if "additive" in meta)
    print(f"ok: {tagged} marts tagged, no Cube measure aggregates a non-additive column")


if __name__ == "__main__":
    main()
