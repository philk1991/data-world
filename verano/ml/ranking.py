"""Module 6 — Blended ranking / re-ranking.

Combines every upstream signal into one scored list per customer:
  - collaborative filtering   (ml.cf_recommendations)
  - co-purchase of their recent items (ml.item_co_purchase)
  - popularity                (ml.popularity_scores)
  - embedding similarity      (customer vec · product-group vec)
Each signal is min-max normalised within the candidate set, blended with fixed,
documented weights, then the winning product GROUP is expanded to a concrete
in-stock variant in the customer's size (availability is a hard filter).

A transparent weighted blend (not a learned re-ranker) is deliberate — it's
explainable and shows each signal's contribution. The production step would be a
learned LTR model (e.g. LightGBM) trained on implicit feedback.

    task verano:ml:ranking
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import mlbase as M

WEIGHTS = {"cf": 0.40, "copurchase": 0.25, "embedding": 0.20, "popularity": 0.15}
TOP_N = 20
RECENT_SEED = 5      # customer's recent groups used to seed co-purchase candidates


def _norm(d: dict[str, float]) -> dict[str, float]:
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    if hi <= lo:
        return {k: 0.0 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}


def build() -> None:
    con = M.connect()

    cf = con.execute("select customer_id, product_group_id, score from ml.cf_recommendations").df()
    cop = con.execute("""select product_group_id, neighbour_product_group_id, score
                         from ml.item_co_purchase""").df()
    popg = con.execute("""select product_group_id, sum(popularity_score) as pop
                          from ml.popularity_scores group by 1""").df()
    pemb = con.execute("select product_group_id, embedding from ml.product_embeddings").df()
    cemb = con.execute("select customer_id, embedding from ml.customer_embeddings").df()

    # Lookups.
    cf_by_cust: dict[str, dict[str, float]] = {}
    for c, g, s in cf.itertuples(index=False):
        cf_by_cust.setdefault(c, {})[g] = s
    cop_by_group: dict[str, list[tuple[str, float]]] = {}
    for g, ng, s in cop.itertuples(index=False):
        cop_by_group.setdefault(g, []).append((ng, s))
    pop_group = dict(zip(popg["product_group_id"], popg["pop"]))
    pop_norm = _norm(pop_group)
    pop_top = [g for g, _ in sorted(pop_group.items(), key=lambda kv: -kv[1])[:30]]
    gvec = {g: np.asarray(v, float) for g, v in zip(pemb["product_group_id"], pemb["embedding"])}
    cvec = {c: np.asarray(v, float) for c, v in zip(cemb["customer_id"], cemb["embedding"])}

    # Customer home size + recent browsed groups.
    home = dict(con.execute("select customer_id, home_size from gold.gold_customer_360").df().itertuples(index=False))
    recent = con.execute("""
        select customer_id_extended as customer_id, p.product_group_id, count(*) as w
        from gold.fact_event fe join gold.dim_product p on fe.product_id = p.variant_id
        where fe.customer_id_extended is not null and fe.event_type in ('page_view','add_to_cart')
        group by 1, 2
    """).df()
    recent_by_cust: dict[str, list[str]] = {}
    for c, grp in recent.sort_values("w", ascending=False).groupby("customer_id"):
        recent_by_cust[c] = grp["product_group_id"].head(RECENT_SEED).tolist()

    # In-stock variant options per group (for group -> SKU expansion).
    variants = con.execute("""
        select product_group_id, variant_id, style_name, category_id, size, price
        from gold.dim_product where is_in_stock and is_active
    """).df()
    var_by_group: dict[str, list[dict]] = {}
    for r in variants.to_dict("records"):
        var_by_group.setdefault(r["product_group_id"], []).append(r)

    def expand(group: str, size: str | None):
        opts = var_by_group.get(group)
        if not opts:
            return None
        in_size = [v for v in opts if v["size"] == size]
        return (in_size or opts)[0]

    rows = []
    for cust, cvector in cvec.items():
        cf_scores = cf_by_cust.get(cust, {})
        seeds = recent_by_cust.get(cust, [])
        cp_scores: dict[str, float] = {}
        for s in seeds:
            for ng, sc in cop_by_group.get(s, []):
                cp_scores[ng] = max(cp_scores.get(ng, 0.0), sc)

        # Candidate groups = CF ∪ co-purchase ∪ popularity backfill.
        cands = set(cf_scores) | set(cp_scores) | set(pop_top)
        cands -= set(seeds)                      # don't recommend what they just browsed
        if not cands:
            continue

        emb_scores = {g: float(cvector @ gvec[g]) for g in cands if g in gvec}
        cf_n, cp_n = _norm({g: cf_scores.get(g, 0.0) for g in cands}), _norm({g: cp_scores.get(g, 0.0) for g in cands})
        emb_n = _norm(emb_scores)
        pop_n = _norm({g: pop_norm.get(g, 0.0) for g in cands})

        scored = []
        for g in cands:
            blended = (WEIGHTS["cf"] * cf_n.get(g, 0.0)
                       + WEIGHTS["copurchase"] * cp_n.get(g, 0.0)
                       + WEIGHTS["embedding"] * emb_n.get(g, 0.0)
                       + WEIGHTS["popularity"] * pop_n.get(g, 0.0))
            scored.append((g, blended, cf_n.get(g, 0.0), cp_n.get(g, 0.0),
                           emb_n.get(g, 0.0), pop_n.get(g, 0.0)))
        scored.sort(key=lambda x: -x[1])

        for rank, (g, blended, a, b, c, d) in enumerate(scored[:TOP_N], start=1):
            v = expand(g, home.get(cust))
            if v is None:
                continue
            rows.append((cust, g, v["variant_id"], v["style_name"], v["category_id"],
                         v["size"], round(v["price"], 2), round(blended, 4),
                         round(a, 3), round(b, 3), round(c, 3), round(d, 3), rank))

    cols = ["customer_id", "product_group_id", "variant_id", "style_name", "category_id",
            "size", "price", "final_score", "cf_score", "copurchase_score",
            "embedding_score", "popularity_score", "rank"]
    recs = pd.DataFrame(rows, columns=cols)
    # Re-rank ranks after any group-expansion drops.
    recs["rank"] = recs.groupby("customer_id")["final_score"].rank(ascending=False, method="first").astype(int)
    M.write_ml_table(con, "ranked_recommendations", recs)

    print(f"  coverage: {recs['customer_id'].nunique():,} customers with ranked recommendations")

    M.rule("Example ranked list + signal ablation (one customer)")
    ex = recs["customer_id"].iloc[0]
    print(f"  customer {ex} (size {home.get(ex)}):")
    show = recs[recs["customer_id"] == ex].head(8)[
        ["rank", "style_name", "category_id", "size", "final_score",
         "cf_score", "copurchase_score", "embedding_score", "popularity_score"]]
    print(show.to_string(index=False))
    con.close()


if __name__ == "__main__":
    build()
