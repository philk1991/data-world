# Integrate nao (open-source analytics agent) — zero added cost

## Context

nao (`getnao/nao`, Apache 2.0) is a self-hosted "agentic analytics agent": a CLI (`nao-core`) builds a file-system-based **context** (schema docs, metrics, rules) on top of a data warehouse, and a chat UI lets people ask natural-language questions that nao turns into SQL against that warehouse. It's a natural fit next to Cube in this repo — both are read-only consumers of the dbt mart layer, and CLAUDE.md already documents that pattern for Cube (`## Semantic layer (Cube)`).

The goal is to stand up nao against the **NBA mart** (user's chosen starting scope) with **zero added cost**:
- nao itself is free/open-source and self-hosted — no SaaS fee.
- The LLM provider will be **local Ollama** (`qwen2.5:14b`, user's chosen model) — nao supports Ollama as a first-class provider with no API key and no per-token charge. This trades some agentic reliability for $0 marginal cost; the plan calls this out honestly rather than silently.
- No Docker — Docker isn't installed on this machine. nao-core is a `pip`-installable CLI and `nao chat` runs the UI directly (Docker is only shown in nao's docs as one deployment option for production/cloud, not a requirement for local use), so we avoid adding a new dependency. This is called out as an open question to verify at setup time (see Risks).

This plan follows the same shape as the Cube integration: a new top-level directory (`nao/`), an `.env`-driven config, new Taskfile entries, and a CLAUDE.md section documenting the operational caveats (chiefly: DuckDB single-writer contention, same class of warning already written for Cube).

## What gets added

### 1. `nao/` project directory (new, analogous to `cube/`)

Scaffolded via `nao init` (not hand-written), then edited:

- `nao/nao_config.yaml` — main config:
  - `databases:` one entry, `type: duckdb`, `path:` pointing at `data/spotify.duckdb` (absolute path via env var, matching this repo's convention — see `.env.example`), scoped with `include: ["marts.nba_*"]` (or the equivalent pattern for the 6 NBA mart tables: `nba_game_results`, `nba_player_advanced_career`, `nba_player_career_stats`, `nba_player_season_stats`, `nba_team_advanced_profile`, `nba_team_dim`, `nba_team_head_to_head`, `nba_team_season_summary`) so nao's context stays scoped to NBA only, per the user's choice.
  - `llm:` `provider: ollama`, `model: qwen2.5:14b` (no `api_key` needed).
  - No `repos:` or `slack:`/`notion:` sections initially — kept out of scope.
- `nao/RULES.md` — agent instructions: NBA-specific grain/definitions distilled from `dbt/models/marts/nba/marts_nba.yml` docs (e.g. season derivation, mid-season trade handling, game_type splits — the same nuance already documented in `cube/model/cubes/nba_player_season_stats.yml`).
- `nao/.env.example` (mirroring `cube/.env.example`) — documents `NAO_DUCKDB_PATH` (absolute path requirement, same convention as `DUCKDB_PATH`/`CUBEJS_DB_DUCKDB_DATABASE_PATH`) and confirms no LLM API key needed for Ollama.
- `nao/.gitignore` — exclude `nao/context/` sync output and any local secrets, matching `cube/.gitignore` pattern (mirrors how `cube/.cubestore/` is excluded).
- `nao/tests/` — one or two `nao test` YAML cases (question + expected SQL) against `marts.nba_player_season_stats`, e.g. reusing a known-good query pattern, to exercise the reliability-testing feature (`nao test`).
- Custom context: copy/adapt the descriptions already in `dbt/models/marts/nba/marts_nba.yml` and `cube/model/cubes/nba_*.yml` into a `nao/docs/nba/` markdown file, since nao's context builder explicitly supports hand-authored Markdown/YAML "custom context" alongside auto-synced DB schema — this reuses existing documentation rather than re-deriving it.

### 2. Taskfile.yml — new tasks (grouped under a new `# ── nao (analytics agent) ──` section, after the Cube section)

- `nao:install` — `pip install nao-core` into the shared `.venv` (mirrors how `dagster:install` extends the same venv, rather than creating a separate one, since nao-core is Python).
- `nao:sync` — `cd nao && nao sync` (refresh context from the DuckDB schema).
- `nao:dev` — `cd nao && nao chat` (start chat UI at localhost:5005), with a `desc:` warning matching the Cube one verbatim in spirit: don't run alongside `task dbt:run` or the NBA Dagster ingest job, since nao's DuckDB connector will hold the file open while syncing/chatting (needs verification — see Risks).
- `nao:test` — `cd nao && nao test` (run the reliability test suite).

### 3. CLAUDE.md — new section

Add `### Analytics agent (nao)` under the existing `## Architecture` heading (sibling to `### Semantic layer (Cube)`), documenting:
- What it is and why it's separate from Cube (nao answers ad-hoc NL questions over the marts; Cube serves defined metrics to BI tools/dashboards — complementary, not competing).
- It reads `marts.nba_*` in `spotify.duckdb` directly, like Cube — same file, same single-writer hazard, so the same "don't run concurrently with `dbt:run`/Dagster NBA ingest" rule applies.
- LLM provider is local Ollama (`qwen2.5:14b`) — zero cost, run entirely offline; note this is a deliberate trade against reliability, and swapping in a paid provider (Anthropic/OpenAI key in `nao/nao_config.yaml`) is a one-line change if quality is insufficient later.
- Not wired into Dagster, for the same reason Cube isn't: it materializes nothing, it only reads.

### 4. `.env.example` (root) — add a pointer

A short comment block like the existing Cube one:
```
# nao analytics agent — lives in its own nao/.env, not this file.
# See nao/.env.example for the full set of NAO_* vars.
```

## Setup sequence (to run after plan approval)

1. `task nao:install` (adds `nao-core` to `.venv`).
2. `pip show nao-core` / `nao --version` sanity check.
3. `ollama pull qwen2.5:14b` (~9GB download, one-time, free).
4. `cd nao && nao init` scaffold, then hand-edit `nao_config.yaml`/`RULES.md` per above.
5. `nao debug` — validate config; **this is where we confirm/resolve the two open risks below** before going further.
6. `task nao:sync`, then `task nao:dev`, ask a handful of NBA questions to sanity-check against known mart values.
7. Author 2-3 `nao test` cases, run `task nao:test`.
8. Update CLAUDE.md and Taskfile as described.

## Risks / open questions to resolve during setup (not blocking the plan, but flagged honestly)

- **DuckDB lock behavior unverified**: nao's docs don't state whether its DuckDB connector opens the file read-only or read-write (Cube's does the latter, which is why Cube carries its warning). Treat it as read-write until `nao debug`/`nao sync` prove otherwise, and apply the same "don't run concurrently with writers" rule as Cube.
- **Local session storage unverified**: nao's production self-hosting guide requires Postgres, but the quickstart (`pip install nao-core` → `nao chat`) doesn't mention it, suggesting local/dev mode may use an embedded store. If `nao chat` errors demanding a `DB_URI`, the fallback is a local Postgres via Homebrew (`brew install postgresql`) — still free/local, no Docker needed.
- **Local model reliability**: `qwen2.5:14b` via Ollama is free but a real step down from Claude/GPT-class models for multi-step agentic SQL generation. The plan builds in `nao test` specifically to quantify this rather than assume it works.

## Verification

- `task nao:dev` starts without error and `nao debug` reports a clean config.
- Chat UI at `http://localhost:5005` answers at least 3 different NBA questions (e.g. "who led the league in points per game in 2023-24?", "which team had the best regular season record?") with SQL that runs against `marts.nba_*` and returns sane results, cross-checked against a manual `duckdb` query.
- `task nao:test` passes the authored test cases.
- Confirm no lock contention: run `task dbt:run` (or the NBA Dagster job) immediately after a `nao sync`/`nao chat` session and confirm it doesn't hang or error — if it does, document the mutual-exclusion rule in CLAUDE.md exactly as done for Cube.
