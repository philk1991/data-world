# Verano — Recommendation & Personalisation Platform (learning build)

A working, inspectable prototype of a 5-layer data platform for a fictional UK
fashion retailer (**Verano**, with brand lines Verano / Petite / Dusk). Built to
*learn the architecture end-to-end* on synthetic data before defending it in a
Head of Data Platform interview — clarity and per-layer inspectability over scale.

It is a self-contained subproject inside `data-world` with its **own dbt project**
and **own DuckDB file** (`verano/data/verano.duckdb`), so it never contends with
`spotify.duckdb`. It reuses the repo's SQL/dbt/yml conventions.

## The 5 layers

| # | Layer | Substitute here | Real design |
|---|---|---|---|
| 1 | Ingestion | Python synthetic generators → bronze | Kafka / Snowpipe streaming + batch |
| 2 | Storage (medallion) | DuckDB schemas bronze → silver → gold | Snowflake |
| 3 | Transformation | dbt (silver → identity → gold) | dbt + Snowpark |
| 4 | ML | scikit-learn / sentence-transformers | Snowpark ML |
| 5 | Serving | FastAPI over precomputed tables | reverse-ETL + online store |

### Medallion ↔ repo-convention mapping

| Medallion (here) | Repo convention | Written by | Materialisation |
|---|---|---|---|
| `bronze_*` (raw landed, immutable) | `raw_*` sources | data-generation scripts | tables (full-replace per seeded run) |
| `silver_*` (cleaned, typed, conformed) | `staging_*` | dbt | views |
| `identity` (bridge + graph) | `intermediate` | dbt | tables |
| `gold` (business marts) | `marts` | dbt | tables |

> **Bronze = generator output.** In medallion terms bronze is "raw landed"; in dbt
> terms that's a *source*, not a model — so the generators own the `bronze_*`
> schemas and dbt begins at silver, reading them via `{{ source() }}`.

## Layout

```
verano/
  data-generation/   # Layer 1 — writes bronze_*  (config.py is the "dial panel")
  dbt/               # Layers 2–3 — own dbt project (profile: verano)
  ml/                # Layer 4 — six inspectable modules (writes ml_*)
  serving/           # Layer 5 — FastAPI, reads verano.duckdb READ-ONLY
  data/verano.duckdb
```

## Running it

Everything is a `task verano:*` command (run from the repo root). Build and
inspect one layer at a time.

```bash
# Layer 1 — synthetic data → bronze
task verano:gen:all         # regenerate all bronze tables (deterministic, seeded)
task verano:gen:profile     # sanity summary: counts, identification rate, spikes, returns

# Layers 2–3 — dbt
task verano:dbt:debug
task verano:dbt:build       # silver → identity → gold, then tests

# Full refresh
task verano:refresh         # gen:all + dbt:build
```

Config lives in `verano/.env` (copy from `.env.example`) — DuckDB path, seed, and
the simulation window. Shift the window ~6 months to land on summer wedding/occasion
season instead of Christmas.

## Bronze tables (Layer 1, built)

| Schema.table | Grain | Notes |
|---|---|---|
| `bronze_catalogue.categories` | category node | 2-level department → leaf hierarchy |
| `bronze_catalogue.products` | product group (style) | parent of variants; has description (for embeddings) |
| `bronze_catalogue.product_variants` | **variant / SKU** | colour × size; UK sizing incl. petite; stock |
| `bronze_customers.customer_versions` | customer × version | SCD source — consent/size/tier/region changes |
| `bronze_events.events` | web event | page_view/search/add_to_cart/purchase + identity signals |
| `bronze_orders.orders` / `order_lines` | order / line | first-party; returns concentrated in occasionwear/denim |
| `bronze_orders.marketplace_orders` / `..._lines` | Mirakl order / line | **different schema** — reconcile in silver |
| `bronze_search.search_logs` | search | query, results, click position, converted |
| `bronze_email.email_events` | email event | sent/open/click; click carries `encoded_customer_id` |

### Identity signals planted in `bronze_events` (the crown jewel for Layer 3)

`customer_id` is populated **only** on deterministic-signal events, so resolving a
browsing session to a customer is a real join problem:

- **Deterministic** — `login`, `email_click` (encoded id), `loyalty_signup`,
  `purchase` (checkout email capture). ~20% of sessions identify.
- **Probabilistic** (to be derived in Layer 3) — persistent cookie (`anonymous_id`
  reused across sessions), IP + user-agent similarity. Cookie churn and shared
  household IPs add realistic noise.

Every event also carries hidden `_true_customer_id` / `_true_session_id`
(underscore-prefixed) that resolution logic must **not** use — they exist so Layer
3 can measure identity precision/recall and sessionization accuracy.

## Modelling decisions worth defending

- **Petite is a brand line + size range, not a category.** The brief lists "Petite
  range" among categories, but it really cross-cuts the clothing categories; modelling
  it as `brand_line = 'Petite'` + `size_range = 'petite'` is cleaner and truer.
- **SCD via a versions table, not dbt snapshots.** A one-shot synthetic build can't
  rely on dbt snapshots capturing change over successive runs, so the generator emits
  explicit customer versions and gold builds the Type-2 dimension (valid_from/valid_to)
  from them. In production you'd use dbt snapshots (or Snowflake streams) — same shape.
- **Guest orders** keep `customer_id` null (anonymous checkout) — they stay
  unidentified, which is realistic and keeps the identification rate honest.

## Substitution flags — translate back to the Snowflake design

1. **DuckDB vs Snowflake** — single node; no warehouse elasticity, RBAC, data
   sharing, zero-copy clone or native time-travel. Bronze immutability is convention
   (deterministic full-replace) not Snowflake streams/time-travel.
2. **Batch generator vs Kafka** — no true event-time/watermarks.
3. **FastAPI over precomputed tables vs reverse-ETL/online store** — our DuckDB read
   is the online serving store; the offline/online split is the same shape.
4. **sklearn/pandas vs Snowpark ML** — same algorithms, different locality/governance.
5. **SQL identity resolution vs a CDP** — the confidence-tier modelling is the
   transferable idea; production adds a CDP/graph store + consent enforcement.

## Build status

- [x] **Layer 1** — synthetic data → bronze (`task verano:gen:all` / `gen:profile`)
- [x] **Layer 2** — silver dbt models (`task verano:dbt:build --select silver`): typed/conformed
      views per bronze table, 30-min-gap sessionization (99.96% session purity vs
      ground truth), and the Mirakl → canonical order reconciliation
- [x] **Layer 3** — identity resolution (`task verano:dbt:build --select identity`,
      score with `task verano:identity:eval`). `bridge_identity` (deterministic +
      probabilistic tiers) + `identity_graph` (strict vs extended keys). Measured vs
      ground truth: deterministic **100% precision**; `device_fingerprint` **62%**;
      `shared_ip` **0%** (pure household-IP noise — the case for tiering). Strict key
      100% precision / 82% recall; extended key 84% / 89% — the precision↔recall dial.
- [x] **Layer 4** — gold marts (`task verano:dbt:build --select gold`): `dim_customer`
      (Type-2 SCD, one current row/customer), `dim_product` (1,939 variants) + `dim_category`,
      `fact_order`/`fact_order_line` (first-party + marketplace unioned), `fact_event`/`fact_search`
      (identity-resolved), `gold_session_summary`, `fact_customer_engagement`, and `gold_customer_360`
- [ ] Layer 5 — ML modules (popularity → co-purchase → CF → propensity → embeddings → ranking)
- [ ] Layer 6 — FastAPI serving
- [ ] Stretch — Dagster asset graph
