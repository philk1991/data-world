"""Check that columns shared across a domain's dbt models take one description.

A column that appears in more than one model of a domain (e.g. season_start_year
in five NBA models) must take its description from a doc block in
models/docs/<domain>.md, so the wording cannot drift between models. Rules:

1. Every shared column references a doc block: description: "{{ doc('nba__x') }}",
   optionally followed by model-specific context.
2. A shared column references the same block in every model, unless every block
   it uses is a named variant, <domain>__<column>__<variant> — the escape hatch for
   columns that share a name but not a meaning (games_played on a player mart vs
   a head-to-head mart).
3. Every block in the domain's docs file is referenced somewhere.

Reads the YAML and Markdown directly, so it needs no dbt parse.

Usage: python scripts/check_column_docs.py [domain ...]   (default: nba)
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
DOC_REF = re.compile(r"""doc\(\s*['"]([^'"]+)['"]\s*\)""")
DOC_DEF = re.compile(r"{%-?\s*docs\s+(\w+)\s*-?%}")


def check(domain: str) -> list[str]:
    docs_file = MODELS_DIR / "docs" / f"{domain}.md"
    defined = set(DOC_DEF.findall(docs_file.read_text())) if docs_file.exists() else set()

    # column -> model -> doc blocks referenced in its description
    columns: dict[str, dict[str, list[str]]] = defaultdict(dict)
    referenced: set[str] = set()
    for yml in sorted(MODELS_DIR.glob(f"*/{domain}/*.yml")):
        for model in (yaml.safe_load(yml.read_text()) or {}).get("models", []):
            for column in model.get("columns", []):
                refs = DOC_REF.findall(column.get("description") or "")
                columns[column["name"]][model["name"]] = refs
                referenced.update(refs)

    errors = []
    for name, models in sorted(columns.items()):
        if len(models) < 2:
            continue
        inline = sorted(m for m, refs in models.items() if not refs)
        if inline:
            errors.append(f"{name}: shared by {len(models)} models but inline in {', '.join(inline)}")
            continue
        blocks = {refs[0] for refs in models.values()}
        variant_prefix = f"{domain}__{name}__"
        if len(blocks) > 1 and not all(b.startswith(variant_prefix) for b in blocks):
            usage = "; ".join(f"{m}: {refs[0]}" for m, refs in sorted(models.items()))
            errors.append(f"{name}: different doc blocks ({usage}). "
                          f"Use one block, or name each {variant_prefix}<variant>")

    errors += [f"doc block {b} is referenced but not defined in {docs_file.name}"
               for b in sorted(referenced - defined) if b.startswith(f"{domain}__")]
    errors += [f"doc block {b} in {docs_file.name} is not used by any model"
               for b in sorted(defined - referenced)]
    return errors


def main() -> int:
    domains = sys.argv[1:] or ["nba"]
    failed = False
    for domain in domains:
        errors = check(domain)
        if errors:
            failed = True
            print(f"{domain}: {len(errors)} column doc problem(s)")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"{domain}: shared column descriptions all come from doc blocks")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
