# Move nao to a free hosted model

Status: planned, not started (5 Nov 2026).

## Context

nao chats through a local Ollama model (`nao-qwen3:14b`, 32K context, `nao/Modelfile`). It costs nothing and keeps everything on the machine, but it has two problems:

- **Slow.** A question takes minutes. nao runs an agent loop (write SQL, run it, chart it, answer), and each step re-sends a prompt of about 11K tokens to a 14B model on a laptop.
- **Unreliable.** On the Stephen Curry shot-zone question it wrote `<display_chart .../>` markup into its answer instead of calling the `display_chart` tool, so no chart appeared. It also read `field_goal_pct_vs_league` 0.057 as "57% better" (it's 5.7 percentage points) and misread `league_share_of_attempts`. RULES.md now covers all three (`97c9284`), but a 14B model doesn't follow rules reliably.

A hosted model should fix both. The data is public NBA stats, and the only other things sent are the schema and `RULES.md`, so a free tier that may use prompts for training is acceptable.

## Free options considered

Check each provider's current free-tier limits before choosing: they change often, and the notes below are from memory.

| Provider | nao provider | For | Against |
|---|---|---|---|
| **Google Gemini** (AI Studio key, Flash) | `gemini` (native) | Good at tool calling and SQL, large context window, fast, the most generous free tier | Free-tier prompts may be used to improve Google's products |
| Groq | `openaiCompatible` | Very fast (Llama, Qwen, gpt-oss) | Free tokens-per-minute caps are tight against an 11K-token prompt |
| OpenRouter `:free` models | `openrouter` (native) | One key, many models: good for comparing | Low daily request limit; models can be slow or unavailable when busy |
| Mistral (free "Experiment" plan) | `mistral` (native) | Decent tool calling | Phone verification; data may be used for training |

Skip Cerebras and GitHub Models: their per-request input caps look smaller than nao's prompt.

**Budget in requests, not questions.** One question is 3–6 model calls, so a limit of 50 requests a day is fewer than 15 questions.

**Recommendation: Gemini Flash on the free tier.** If the limits bite, paid small models (Gemini Flash, GPT-4o-mini) cost a fraction of a cent per question.

## Steps

1. [ ] Check Gemini's current free-tier limits (requests per minute and per day, tokens per minute) against about 5 calls of about 11K tokens per question.
2. [ ] Create a key at aistudio.google.com. Add it to `nao/.env`, and add a commented `GEMINI_API_KEY` line (or whatever name nao 0.3.31 reads) to `nao/.env.example`.
3. [ ] In `nao/nao_config.yaml`, add a `gemini` provider under `llm.providers` and make it the default. Keep the `ollama` provider as a second, non-default option so switching back is a one-line change. Check the exact provider and model-id spelling nao 0.3.31 accepts with `task nao:debug`.
4. [ ] Restart nao (`task nao:dev`). In a **new** chat, re-ask the Curry 2015-16 shot-zone question. Pass if:
   - a chart renders (a `tool-display_chart` part appears in `nao/db.sqlite` → `message_part`);
   - the query filters `game_type = 'Regular Season'`, so 6 rows;
   - it describes `_vs_league` as percentage points;
   - it says about 45% of his attempts were inside the arc (712 of 1,598).
5. [ ] Re-ask a clutch question (e.g. the 2025-26 clutch points leaders; expect SGA at 175, then Murray at 166) and time it against Ollama.
6. [ ] If Gemini's limits don't hold up, try OpenRouter with a free model, then Groq through `openaiCompatible`.
7. [ ] Update the docs:
   - CLAUDE.md's "Local LLM" caveat under *Analytics agent (nao)*: hosted default, Ollama as fallback, key in `nao/.env`;
   - `nao/.env.example`;
   - the README, if it mentions the model.
8. [ ] Optional: if Ollama is no longer used, note that `task nao:model` and the ~9 GB `nao-qwen3:14b` model can be removed. Keep them for offline use otherwise.

## Out of scope

- Adding hosted models to Cube's MCP server or any other component.
- Paid models, unless the free tiers turn out to be unusable.
