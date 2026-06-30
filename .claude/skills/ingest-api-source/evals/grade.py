#!/usr/bin/env python3
"""
Grade one generated ingestion pipeline copy against an eval's assertions.

Runs the generated entry point twice against a fresh throwaway DuckDB (so row
counts + idempotency are measured, not trusted), introspects the resulting raw
tables, and inspects the source files for naming / fetch_-load_ / incremental
conventions. Writes grading.json with {text, passed, evidence} per assertion.

Usage:
    python grade.py --copy <data-world path> --eval <0|1|2> --out <grading.json>
"""
import argparse, json, os, re, subprocess, sys, tempfile, glob
from pathlib import Path

ORIGINAL_ENTRYPOINTS = {"ingest.py", "ingest_nba.py", "ingest_statsbomb.py"}
VENV_PY = None  # resolved from copy


def find_entrypoints(di: Path):
    return [p for p in di.glob("ingest_*.py") if p.name not in ORIGINAL_ENTRYPOINTS] \
         + [p for p in di.glob("ingest.py") if p.name not in ORIGINAL_ENTRYPOINTS]


def run_entrypoint(copy: Path, entry: Path, db_path: str):
    """Run `python <entry>` from data-ingestion/ with DUCKDB_PATH overridden."""
    env = dict(os.environ, DUCKDB_PATH=db_path)
    proc = subprocess.run(
        [VENV_PY, entry.name],
        cwd=str(copy / "data-ingestion"),
        env=env, capture_output=True, text=True, timeout=300,
    )
    return proc.returncode, proc.stdout + "\n" + proc.stderr


def introspect(db_path: str):
    """Return {schema.table: {rows, columns:{name:type}}} for raw_ tables."""
    import duckdb
    out = {}
    if not os.path.exists(db_path):
        return out
    c = duckdb.connect(db_path, read_only=True)
    tabs = c.execute(
        "select schema_name, table_name from duckdb_tables() where schema_name like 'raw_%' order by 1,2"
    ).fetchall()
    for s, t in tabs:
        cols = c.execute(
            "select column_name, data_type from duckdb_columns() where schema_name=? and table_name=?",
            [s, t]).fetchall()
        n = c.execute(f'select count(*) from "{s}"."{t}"').fetchone()[0]
        out[f"{s}.{t}"] = {"rows": n, "columns": {cn: ct for cn, ct in cols}}
    c.close()
    return out


def grade(copy: Path, eval_id: int):
    global VENV_PY
    VENV_PY = str(copy / ".venv" / "bin" / "python")
    di = copy / "data-ingestion"
    entries = find_entrypoints(di)
    source_files = "\n".join(
        p.read_text(errors="ignore") for p in di.rglob("*.py")
        if p.name not in ("__init__.py",) and "ingest" in str(p) or "/ingestion/" in str(p).replace("\\", "/")
    )
    all_py = "\n".join(p.read_text(errors="ignore") for p in di.rglob("*.py"))
    taskfile = (copy / "Taskfile.yml").read_text(errors="ignore")

    # Run the pipeline (twice for idempotency) against throwaway DBs.
    db1 = tempfile.mktemp(suffix=".duckdb")
    rc1 = rc2 = None; log1 = log2 = ""
    tables1 = {}; tables2 = {}
    if entries:
        entry = entries[0]
        rc1, log1 = run_entrypoint(copy, entry, db1)
        tables1 = introspect(db1)
        # second run on SAME db → idempotency
        rc2, log2 = run_entrypoint(copy, entry, db1)
        tables2 = introspect(db1)
    # Fallback: if nothing landed in throwaway (pipeline ignored DUCKDB_PATH),
    # inspect whatever the subagent populated in the copy's default DBs.
    if not tables1:
        for dbf in glob.glob(str(copy / "data" / "*.duckdb")):
            tables1.update(introspect(dbf))

    A = []  # assertions: (id, text, passed, evidence)

    def schemas(): return {k.split(".")[0] for k in tables1}
    def tnames(): return list(tables1.keys())
    def has_col(substr):
        return any(any(substr in cn.lower() for cn in v["columns"]) for v in tables1.values())
    def ingested_at_type():
        types = []
        for v in tables1.values():
            for cn, ct in v["columns"].items():
                if cn.lower() == "ingested_at":
                    types.append(ct)
        return types

    raw_schema = next((s for s in schemas()), None)
    # Source slug from the entry point: ingest_<source>.py -> <source>
    source = entries[0].name[len("ingest_"):-3] if entries else None

    # Shared assertions
    A.append(("schema_naming", "Raw data lands in a raw_<source> schema",
              bool(schemas()) and all(s.startswith("raw_") for s in schemas()),
              f"schemas={sorted(schemas())}"))
    # Convention: table name itself carries the source prefix -> raw_<source>_<entity>
    table_parts = [k.split(".", 1)[1] for k in tnames()]
    naming_ok = bool(source) and bool(table_parts) and all(
        t.startswith(f"raw_{source}_") for t in table_parts)
    A.append(("table_naming",
              "Tables follow raw_<source>_<entity> (source-prefixed table name)",
              naming_ok,
              f"source={source}; tables={table_parts}"))
    readme = (copy / "README.md").read_text(errors="ignore")
    di_readme = (copy / "data-ingestion" / "README.md").read_text(errors="ignore")
    readme_ok = bool(source) and source in readme.lower()
    A.append(("readme_wired", "Source documented in README.md (root)",
              readme_ok, f"in_root_readme={source in readme.lower() if source else None}; "
                         f"in_di_readme={source in di_readme.lower() if source else None}"))
    iat = ingested_at_type()
    A.append(("ingested_at", "Every raw table has ingested_at TIMESTAMPTZ",
              bool(iat) and all("TIMESTAMP" in t.upper() for t in iat) and len(iat) == len(tables1),
              f"ingested_at types={iat}, n_tables={len(tables1)}"))
    A.append(("entrypoint", "An ingest_<source>.py entry point exists at data-ingestion/",
              bool(entries), f"entrypoints={[e.name for e in entries]}"))
    fetch_defs = re.findall(r"def (fetch_\w+)", all_py)
    load_defs = re.findall(r"def (load_\w+)", all_py)
    A.append(("fetch_load_pair", "Modules expose fetch_/load_ functions",
              bool(fetch_defs) and bool(load_defs),
              f"fetch_defs={fetch_defs}; load_defs={load_defs}"))
    A.append(("runs_ok", "Pipeline runs without error",
              rc1 == 0, f"returncode={rc1}; log_tail={log1[-300:]!r}"))

    if eval_id == 0:
        task_ok = "ingest:jsonplaceholder" in taskfile
        posts = next((v["rows"] for k, v in tables1.items() if "post" in k), None)
        users_tbl = next((v for k, v in tables1.items() if "user" in k), None)
        users = users_tbl["rows"] if users_tbl else None
        # flatten check: a users table should have > ~5 scalar cols and a city/street/company col,
        # and no column typed as STRUCT/JSON/MAP holding a whole nested object.
        flat_ok = False; flat_ev = "no users table"
        if users_tbl:
            ucols = users_tbl["columns"]
            nested_typed = [c for c, t in ucols.items() if any(x in t.upper() for x in ("STRUCT", "JSON", "MAP", "[]"))]
            scalar_nested = any(any(k in c.lower() for k in ("city", "street", "zip", "company", "lat", "lng", "suite", "geo"))
                                for c in ucols)
            flat_ok = scalar_nested and not nested_typed
            flat_ev = f"user_cols={list(ucols)}; nested_typed={nested_typed}"
        A.append(("taskfile", "ingest:jsonplaceholder task added", task_ok, f"present={task_ok}"))
        A.append(("runs_posts_100", "posts table has exactly 100 rows", posts == 100, f"posts_rows={posts}"))
        A.append(("runs_users_10", "users table has exactly 10 rows", users == 10, f"users_rows={users}"))
        A.append(("nested_flattened", "Nested address/company flattened to scalar columns", flat_ok, flat_ev))

    elif eval_id == 1:
        task_ok = "ingest:pokeapi" in taskfile
        poke = next((v for k, v in tables1.items() if "pokemon" in k or "poke" in k), None)
        rows = poke["rows"] if poke else None
        cols = list(poke["columns"]) if poke else []
        A.append(("taskfile", "ingest:pokeapi task added", task_ok, f"present={task_ok}"))
        A.append(("pagination_worked", "pokemon table > 1000 rows (paged through all)",
                  bool(rows) and rows > 1000, f"pokemon_rows={rows}"))
        A.append(("name_url_cols", "table has name + url columns",
                  poke is not None and any("name" in c for c in cols) and any("url" in c for c in cols),
                  f"cols={cols}"))

    elif eval_id == 2:
        comments = next((v for k, v in tables1.items() if "comment" in k), None)
        rows1 = comments["rows"] if comments else None
        rows2 = next((v["rows"] for k, v in tables2.items() if "comment" in k), None)
        has_key = comments is not None and any("post" in c.lower() and "id" in c.lower() for c in comments["columns"])
        # Functional incremental check: any get_loaded_* helper + delete-before-insert.
        incr_ok = bool(re.search(r"get_loaded\w*", all_py)) and bool(re.search(r"delete from", all_py, re.I))
        skip_ok = bool(re.search(r"skip", all_py, re.I)) or bool(re.search(r"already", all_py, re.I)) or "loaded" in all_py.lower()
        A.append(("table_naming_post_id", "comments table has a post_id key column", has_key,
                  f"cols={list(comments['columns']) if comments else None}"))
        A.append(("incremental_helper", "get_loaded_ids() + delete-before-insert present", incr_ok,
                  f"get_loaded_ids={'get_loaded_ids' in all_py}, delete={'delete from' in all_py.lower()}"))
        A.append(("skip_on_rerun", "entry point skips already-loaded post_ids", skip_ok,
                  f"skip/already/loaded keyword present={skip_ok}"))
        A.append(("first_run_50", "first run loads 50 comment rows", rows1 == 50, f"rows_after_run1={rows1}"))
        A.append(("idempotent_rerun", "second run = same row count (no duplicates)",
                  rows1 is not None and rows1 == rows2, f"rows_run1={rows1}, rows_run2={rows2}, rc2={rc2}"))

    expectations = [{"text": f"[{aid}] {text}", "passed": bool(p), "evidence": ev} for aid, text, p, ev in A]
    passed = sum(e["passed"] for e in expectations)
    total = len(expectations)
    return {
        "eval_id": eval_id,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": round(passed / total, 3) if total else 0,
        },
        "tables_observed": {k: v["rows"] for k, v in tables1.items()},
        "expectations": expectations,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--copy", required=True)
    ap.add_argument("--eval", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = grade(Path(args.copy), args.eval)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"{args.out}: {result['n_passed']}/{result['n_assertions']} passed")
    for e in result["expectations"]:
        print(("  PASS " if e["passed"] else "  FAIL ") + e["text"])
