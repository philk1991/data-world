"""Fail when an NBA rate formula is written outside its one definition per layer.

Phase 3's acceptance rule (plans/nba-staff-ae-project.md): a rate formula has one
definition in dbt (dbt/macros/nba_metrics.sql, for the rollup and non-additive
marts) and one in Cube (cube/model/macros/nba_rates.jinja, for every measure),
and nao defines none: it reads the columns or asks Cube. task cube:reconcile
checks the dbt and Cube definitions give the same numbers.

A formula is found by its constants: 0.44 (free throw trips in true shooting,
turnover % and usage), `0.5 *` (threes in effective field goal %) and `48 *`
(pace per 48 minutes). Scanned:
- dbt: every .sql file under models/ and macros/;
- Cube: every `sql` value in the model YAML (descriptions may quote formulas);
- nao: RULES.md and the docs under nao/docs/.

Usage: python cube/scripts/check_formulas.py
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFINITIONS = {
    ROOT / "dbt" / "macros" / "nba_metrics.sql",
    ROOT / "cube" / "model" / "macros" / "nba_rates.jinja",
}
FORMULA = re.compile(r"0\.44\b|\b0\.5 \*|\b48(?:\.0)? \*")


def sql_values(node):
    """Every `sql` string in a parsed Cube YAML document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "sql" and isinstance(value, str):
                yield value
            else:
                yield from sql_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from sql_values(item)


def main() -> None:
    hits = []
    for path in sorted((ROOT / "dbt").glob("m*/**/*.sql")):  # models/ and macros/
        if path in DEFINITIONS:
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if FORMULA.search(line) and not line.lstrip().startswith("--"):
                hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    for path in sorted((ROOT / "cube" / "model").rglob("*.yml")):
        for sql in sql_values(yaml.safe_load(path.read_text())):
            if FORMULA.search(sql):
                hits.append(f"{path.relative_to(ROOT)}: {sql.strip()[:120]}")
    for path in [ROOT / "nao" / "RULES.md", *sorted((ROOT / "nao" / "docs").rglob("*.md"))]:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if FORMULA.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:120]}")
    for hit in hits:
        print(hit)
    if hits:
        print(f"\n{len(hits)} formula(s) written outside "
              + " and ".join(str(p.relative_to(ROOT)) for p in sorted(DEFINITIONS))
              + ": call the macro instead.")
        sys.exit(1)
    print("ok: every rate formula lives in its one definition per layer")


if __name__ == "__main__":
    main()
