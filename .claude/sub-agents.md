# Sub-agents in this project

Sub-agents are separate Claude instances that the main agent spawns to handle a discrete
piece of work. Each agent has its own context window, runs its own tools, and returns a
result to the main agent when done.

There are two distinct reasons to use them:

| Reason | When it applies |
|---|---|
| **Parallelism** | Multiple independent tasks that have no dependency on each other's results |
| **Context protection** | A task requires reading a large amount of material that would crowd out the main agent's working context |

---

## Example 1 — Parallel failure diagnosis (`/test-failures`)

**Skill:** `.claude/skills/test-failures.md`

When `/test-failures` runs and finds, say, 6 failing dbt tests, each failure needs a
DuckDB diagnostic query: connect, run a query, format the result. These 6 queries have
no dependency on each other — failure A's result doesn't affect failure B's query.

**Sequential approach (no sub-agents):**
```
query 1 → wait → query 2 → wait → query 3 → wait → ... → assemble report
total time = sum of all query times
```

**Parallel approach (sub-agents):**
```
spawn agent 1 ─┐
spawn agent 2  ├─ all start simultaneously
spawn agent 3  │
...            │
all finish  ───┘ → assemble report
total time = slowest single query
```

**The threshold decision:**
The skill only uses sub-agents for 3 or more failures. Each sub-agent adds ~2 seconds
of spawn overhead. With 2 failures, spawning 2 agents (4s overhead) costs more than
simply running 2 queries sequentially. At 3+, the parallelism saving exceeds the overhead.

```
< 3 failures  →  sequential Python script  (overhead > saving)
≥ 3 failures  →  one sub-agent per failure  (saving > overhead)
```

**Key implementation detail:**
All sub-agents are spawned in a single message — not one at a time. Waiting for each
agent to finish before spawning the next would make execution sequential again.

---

## Example 2 — Parallel table profiling (`/explore-dataset`)

**Skill:** `.claude/skills/explore-dataset.md`

When `/explore-dataset statsbomb` runs, it discovers 4 raw tables: competitions, matches,
events, lineups. Running `SUMMARIZE` on each takes 3–5 seconds per table — 12–20 seconds
sequentially. The profiling of each table is completely independent.

**The threshold decision:**
```
1–2 tables  →  sequential script  (spawn overhead not worth it)
3+ tables   →  one sub-agent per table  (wall-clock time = slowest table, not sum)
```

**What each sub-agent receives:**
- The DuckDB connection details
- The specific `schema.table` ref to profile
- A precise JSON schema to return (so the main agent can merge results cleanly)

**What the main agent does:**
Waits for all sub-agents, merges their JSON results into a single array, then assembles
the full EDA report. The main agent never touched a database — it only reasoned about
the output.

---

## Example 3 — Context protection (`/dbt-develop`)

**Skill:** `.claude/skills/dbt-develop.md`

When `/dbt-develop` scaffolds a new model, it needs the project's dbt, SQL, and YAML
conventions. These three files together are ~300 lines. Reading them all into the main
context before generating any SQL crowds out the space the main agent needs to:
- hold the model's column list and intent
- generate the SQL with precise formatting
- write the YAML with correct meta fields
- validate against the compile output

**The sub-agent pattern:**
An Explore sub-agent reads all three files, then returns a maximum 40-line summary
covering only the rules relevant to the target layer (staging / intermediate / mart).
The main agent works from the compact summary — never sees the raw files.

```
Main agent                     Explore sub-agent
─────────────                  ─────────────────
spawn sub-agent ─────────────► read dbt-conventions.md
(continues collecting           read sql-conventions.md
 intent from user)              read yml-conventions.md
                                filter to target layer
◄─────────────────────────────  return 40-line summary
work from summary
```

This is not about speed — it is about preserving context quality. A main agent that
has read 300 lines of conventions before starting work has less room for the actual
task than one that received a targeted summary.

---

## Decision framework

Before spawning a sub-agent, ask two questions:

**1. Are the tasks independent?**
If task B needs the result of task A, they must be sequential. Sub-agents are only
useful when tasks share no data dependency.

**2. Does the overhead pay off?**
Sub-agent spawn costs ~2s and an LLM call. For parallelism, the break-even is
roughly 3 independent tasks. For context protection, the question is whether the
material being offloaded is large enough to meaningfully affect main context quality.

| Scenario | Use sub-agents? |
|---|---|
| 6 independent DuckDB queries | Yes — parallelism |
| 2 independent DuckDB queries | No — overhead > saving |
| Reading 300 lines of reference material before a complex task | Yes — context protection |
| Reading one short file | No — just read it inline |
| Tasks with shared state or ordering dependencies | Never |
