# ADR 0005: How nao answers questions

Status: accepted (10 Nov 2026)

## Context

nao writes SQL against the marts. A semantic layer answers modelled questions far more reliably and refuses what it can't answer, where text-to-SQL returns a plausible wrong number (dbt Labs 2026 benchmark, `plans/nba-staff-ae-project.md` Part 2.1).

## Decision

- Defined metrics go through Cube, via the Cube MCP server registered in `nao_config.yaml` (Phase 4).
- SQL over the marts is for exploration only, and an answer that came from SQL says so ("from SQL over the marts, not a defined metric").
- Until Phase 4, RULES.md carries the same defaults Cube uses: regular season careers, seasons from 1954-55, `is_qualified` for leaderboards.

## Consequences

nao's rules stop defining thresholds or formulas of their own. They describe scope and route to the definitions in Cube.
