# Verano — Plan for Stages 5–7 (ML · Serving · Orchestration)

Reference doc for the remaining layers. Stages 0–4 (bronze → silver → identity →
gold) are built, committed and green (`dbt build` PASS=165). This document covers:

- **Stage 5** — the six ML modules
- **Stage 6** — the FastAPI serving layer
- **Stage 7** — the Dagster asset graph (stretch)

…plus a **data-readiness audit** and the **pre-flight decisions** to settle before
we start writing ML code.

---

## 0. Pre-flight checklist (do these before Stage 5)

1. **Install dependencies** into the repo `.venv` (keeps `duckdb` pinned at 1.4.4):
   ```bash
   source .venv/bin/activate && pip install -r verano/requirements.txt
   ```
   Needed now: `scikit-learn` (Stage 5), `fastapi` (Stage 6). `uvicorn`, `numpy`,
   `pandas`, `duckdb`, `dagster*` are already present. `sentence-transformers` only
   if decision **D4 = transformers** (else it's skipped).
2. **Settle the pre-flight decisions** in §2 (grain, co-purchase density, propensity
   split, embeddings backend, ranking approach).
3. **Single-writer reminder** — the ML modules open `verano.duckdb` **read-write** to
   write the `ml` schema. Never run `task verano:ml:*` while `task verano:dbt:*`,
   `task verano:serve`, or a Dagster job is also touching the file.

---

## 1. Data-readiness audit (measured on the current dataset)

| Module | Signal available | Verdict |
|---|---|---|
| Popularity | fact_event views/purchases over 6 months | ✅ ready |
| Co-purchase | **816 multi-item baskets, all size-2**; 348 customers with 2+ distinct items bought | ⚠️ thin — see **D2** |
| Collaborative filtering | 3,138 identified customers × 1,939 items × **41,787 interactions** (avg 11.7 items/cust; 2,733 with ≥5) | ✅ ready |
| Propensity | April-cutoff label: 3,119 feature customers, **136 positives (4.4%)** | ⚠️ imbalanced — see **D3** |
| Embeddings | product `description` on dim_product ✓; interaction sequences from fact_event ✓ | ✅ ready |
| Ranking | consumes 1–5; `is_in_stock`/`size` on dim_product ✓ | ✅ ready once 1–5 exist |

---

## 2. Pre-flight decisions

### D1 — Grain for CF / co-purchase / embeddings  ·  **Recommend: product_group_id**
The catalogue is 1,939 variants but only **169 product groups**. Size/colour
variants fragment every signal (a customer who views a dress in 3 sizes looks like
3 items). **Recommendation:** model co-purchase, CF and embeddings at
**product_group grain**, then **expand to a concrete variant at serving time** by
picking an in-stock SKU in the customer's `home_size`. This is both denser and how
real recommenders work (recommend the *style*, resolve the *SKU* at render). Popularity
and ranking still expose variant-level availability.

### D2 — Co-purchase density  ·  **Recommend: combine signals now; optional regenerate**
At product_group grain the 816 same-basket pairs + 348 multi-item customers give a
usable matrix. **Recommendation:** build co-purchase from **both** same-basket pairs
**and** same-customer cross-order pairs, scored by lift/cosine. *Optional upgrade:* a
small generator tweak (baskets of 2–4 items, 1–3 cross-sell complements, higher
`P_CROSS_SELL`) then `task verano:refresh` — denser, more convincing "also bought".
Deterministic, cheap; decide if you want it.

### D3 — Propensity label window  ·  **Recommend: 2-month label + balanced LR**
April-only gives 136 positives (4.4%). **Recommendation:** features from **Nov–Feb**,
label = **purchased in Mar–Apr** (≈2× positives). Use `LogisticRegression(class_weight
='balanced')`, report **ROC-AUC + PR-AUC** (PR-AUC matters at a low base rate), and
print coefficients for interpretability. **Point-in-time features are mandatory** —
`gold_customer_360` RFM is computed over *all* data and would leak; propensity builds
its own as-of-cutoff features in `features.py`.

### D4 — Embeddings backend  ·  **choice**
`sentence-transformers` (all-MiniLM-L6-v2, ~90MB + torch, more convincing NN quality)
**vs** TF-IDF + TruncatedSVD fallback (no heavy deps, fast, fine for teaching).
Controlled by `VERANO_EMBEDDINGS` in `.env`. *Lean:* transformers if you want to
speak to embedding quality in the panel; TF-IDF if you'd rather keep deps light.

### D5 — Ranking model  ·  **Recommend: transparent weighted blend + ablation**
A documented weighted blend of normalised signals (CF + co-purchase + popularity +
embedding similarity) × availability, with an **ablation table** showing each signal's
contribution. Explainable and enough to teach the concept. Note in the panel that the
production step is a **learned LTR re-ranker** (LightGBM/logistic on implicit labels);
we can add that as an optional extension.

### D6 — Dependencies  ·  install `scikit-learn`, `fastapi` (+ `sentence-transformers` iff D4=transformers)

---

## 3. Stage 5 — ML modules

Location `verano/ml/`. Each module is independently runnable (`python ml/<x>.py`)
and via `task verano:ml:<x>`; `task verano:ml:all` runs them in order. Each reads
gold, writes one or more `ml.*` tables, and **prints its eval metric**. Deterministic
seeds throughout. Shared helpers in `features.py` (interaction matrix, point-in-time
RFM, normalisation) and `store.py` (write table + print top-N).

| # | Module → `ml.*` table(s) | Reads | Method | Eval (printed) |
|---|---|---|---|---|
| 1 | `popularity.py` → `popularity_scores` | fact_event, fact_order_line | recent purchase+view weight; trend = recent vs prior-window lift; overall + per-category | top-20 overall, top-5/category; works with no customer input |
| 2 | `co_purchase.py` → `item_co_purchase` | fact_order_line (+customer), fact_event carts | co-occurrence at **product_group** grain (same-basket ∪ same-customer), lift/cosine, top-N neighbours | neighbours for a known dress → accessories appear |
| 3 | `collaborative.py` → `cf_recommendations` (+ factor tables) | fact_event interactions (view=1/cart=3/purchase=5) at product_group grain | implicit-feedback matrix factorisation — sklearn `TruncatedSVD` (k≈32); optional `implicit` ALS | **precision@10 / recall@10** on held-out last interaction |
| 4 | `propensity.py` → `propensity_scores` | point-in-time features (features.py) | temporal split (D3), `LogisticRegression(balanced)` on RFM + engagement | **ROC-AUC + PR-AUC**, coefficients, deciles |
| 5 | `embeddings.py` → `product_embeddings`, `customer_embeddings` | dim_product.description; fact_event sequences | sentence-transformers *or* TF-IDF+SVD (D4); product vec per group; customer vec = weighted mean of interacted groups | NN sniff test: items near a floral occasion dress |
| 6 | `ranking.py` → `ranked_recommendations` | all `ml.*` above + dim_product (stock/size) | per-customer candidates (CF ∪ co-purchase of recent ∪ popularity), normalised weighted blend × availability × size; expand group→variant | final list for one customer + **ablation** table; cold-start → popularity |

**Storage:** embeddings stored as DuckDB `DOUBLE[]` array columns. `ml` schema is
Python-owned (not a dbt model) — same pattern as the identity eval reading gold.

**Tasks to add:** `verano:ml:popularity|copurchase|cf|propensity|embeddings|ranking`,
`verano:ml:all`.

---

## 4. Stage 6 — Serving (FastAPI, read-only DuckDB)

Location `verano/serving/`. `app.py` + `dependencies.py` (a read-only DuckDB
connection dependency — mirrors the repo's read-only dashboard pattern) + `routers/`.
Reads precomputed `ml.*` tables — the offline-compute / online-serve split that stands
in for reverse-ETL + an online store.

| Endpoint | Pattern | Logic |
|---|---|---|
| `POST /search/rerank` | search engine pulls a personalisation score at query time | candidates from query (category/text match on dim_product) or supplied ids → rerank by CF/propensity/embedding-sim × availability; returns scored list + reason |
| `GET /website/recommendations/{customer_id}` | PDP/homepage pull | from `ranked_recommendations`; `?slot=pdp&product_id=` uses `item_co_purchase`; unknown/cold customer → `popularity_scores` fallback |
| `GET /email/batch-export` | batch campaign export | `propensity_scores` + `ranked_recommendations`, **gated to `marketing_consent = true`** (consent governance — reads current SCD consent) |

**Tasks:** `verano:serve` (uvicorn, `--reload`). **Verify:** open `/docs`, curl each
endpoint, confirm the cold-start fallback for an unknown customer, and that the email
export drops non-consented customers.

**Substitution note for the panel:** precomputed DuckDB tables + FastAPI = our stand-in
for a reverse-ETL push (Census/Hightouch) into an online store (Redis/DynamoDB). Same
offline/online shape; different latency/scale.

---

## 5. Stage 7 — Dagster asset graph (stretch)

Location `verano/orchestration/` (small self-contained package; **do not** mix into the
repo's existing `orchestration/` which targets spotify.duckdb). Assets:

```
gen_bronze (generate.py)
   └─> dbt: silver → identity → gold   (@dbt_assets over verano/dbt)
          └─> ml: popularity, co_purchase, cf, propensity, embeddings
                     └─> ranking
                            └─> email_export
```

One `verano_pipeline` job; optional daily schedule. `DAGSTER_HOME` set by the task.
**Task:** `verano:dagster:dev`. **Verify:** the asset graph renders in the Dagster UI
and materialises end-to-end. Keep light — the DAG visual is the deliverable for the
panel, not production scheduling.

---

## 6. Verification summary (per stage)

- **Stage 5:** `task verano:ml:all` → six `ml.*` tables populated; each prints its
  metric (precision@10, ROC/PR-AUC, NN sniff test, ranking ablation).
- **Stage 6:** `task verano:serve`; `/docs`; curl all three endpoints; cold-start +
  consent-gating checks.
- **Stage 7:** `task verano:dagster:dev`; asset graph renders and materialises clean.

---

## 7. Open decisions to confirm before Stage 5

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Model grain for CF/co-purchase/embeddings | **product_group**, expand to variant at serving |
| D2 | Co-purchase density | combine same-basket + same-customer; *optional* denser-basket regenerate |
| D3 | Propensity split | features Nov–Feb, label Mar–Apr; balanced LR; ROC+PR-AUC |
| D4 | Embeddings backend | your call: sentence-transformers *vs* TF-IDF fallback |
| D5 | Ranking model | transparent weighted blend + ablation (LTR noted as production step) |
| D6 | Install deps | scikit-learn, fastapi (+ sentence-transformers iff D4) |
