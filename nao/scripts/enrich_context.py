"""Add the lake's dbt descriptions and column names to nao's context.

Runs after `nao sync` (the nao:sync task does both). Two jobs:

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

Reads the lake READ_ONLY through data-ingestion/lake.py, so LAKE_DATA_PATH must
be set (the Taskfile exports it).

Usage:
  python nao/scripts/enrich_context.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data-ingestion"))

from lake import connect_lake  # noqa: E402

CONTEXT_DIR = ROOT / "nao" / "databases" / "type=ducklake" / "database=lake"
RULES = ROOT / "nao" / "RULES.md"
RULES_HEADING = "## Columns by table (generated)"
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


def write_rules(columns_by_table: dict[str, list[str]]) -> None:
    text = RULES.read_text()
    hand_written = text.split(RULES_HEADING, 1)[0].rstrip("\n")
    RULES.write_text(f"{hand_written}\n\n{rules_section(columns_by_table)}")


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

    write_rules(columns_by_table)
    print(f"Descriptions added to {changed} of {len(tables)} columns.md files; "
          f"RULES.md lists the columns of {len(columns_by_table)} tables.")


if __name__ == "__main__":
    main()
