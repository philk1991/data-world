"""Module 3 — Collaborative filtering (customer-level).

Implicit-feedback CF over the identity graph. Interactions come from the resolved
customer x product-group matrix, confidence-weighted by event type (view=1, cart=3,
purchase=5). We use item-based kNN CF (TF-IDF weighting + top-N item neighbourhoods)
— for this concentrated catalogue it personalises better than an SVD reconstruction,
and it's the intuitive "customers who liked X also liked Y".

Evaluated with a random leave-one-out hold-out against a popularity baseline, so you
can show CF genuinely personalises beyond "just recommend the popular stuff".

    task verano:ml:cf
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.preprocessing import normalize

import mlbase as M

N_NEIGHBOURS = 20        # item-item kNN neighbourhood size
TOP_N = 20               # recommendations stored per customer
EVAL_K = 10


def _cf_scores(matrix: np.ndarray) -> np.ndarray:
    """Item-based kNN collaborative filtering.

    TF-IDF down-weights ubiquitous popular items; items are compared by cosine over
    their (customer) columns; each item keeps only its top-N most similar
    neighbours (this is what stops popular items dominating every recommendation).
    A customer's score for an item is the weighted sum of similarities to the items
    they've actually interacted with — "customers who liked X also liked Y".
    """
    Xw = TfidfTransformer(norm=None).fit_transform(matrix).toarray()
    item_vecs = normalize(Xw, axis=0)                 # unit-norm item columns
    sim = item_vecs.T @ item_vecs                     # item-item cosine
    np.fill_diagonal(sim, 0.0)

    # Keep only each item's top-N neighbours.
    keep = np.argsort(-sim, axis=1)[:, :N_NEIGHBOURS]
    mask = np.zeros_like(sim, dtype=bool)
    mask[np.arange(sim.shape[0])[:, None], keep] = True
    sim *= mask

    return Xw @ sim                                   # customers x items


def build() -> None:
    con = M.connect()

    # Signal from BROWSING (product views + carts), not purchases. Purchases carry
    # the cross-sell mechanic (accessories added to many baskets regardless of
    # taste), which makes those items co-occur with everything and pollutes CF.
    # Views/carts reflect genuine per-customer taste.
    inter = con.execute("""
        select
            customer_id_extended as customer_id,
            p.product_group_id,
            sum(case fe.event_type when 'add_to_cart' then 3 else 1 end) as weight,
            max(fe.event_at) as last_at
        from gold.fact_event fe
        join gold.dim_product p on fe.product_id = p.variant_id
        where fe.customer_id_extended is not null and fe.product_id is not null
          and fe.event_type in ('page_view', 'add_to_cart')
        group by 1, 2
        having weight > 0
    """).df()

    groups_meta = con.execute(
        "select distinct product_group_id, style_name, category_id from gold.dim_product").df()

    customers = sorted(inter["customer_id"].unique())
    groups = sorted(inter["product_group_id"].unique())
    cu = {c: i for i, c in enumerate(customers)}
    gi = {g: i for i, g in enumerate(groups)}
    print(f"CF matrix: {len(customers):,} customers x {len(groups)} product groups, "
          f"{len(inter):,} interactions")

    # Raw confidence matrix (TF-IDF weighting is applied inside _cf_scores).
    X = np.zeros((len(customers), len(groups)), dtype=np.float32)
    rows = inter["customer_id"].map(cu).to_numpy()
    cols = inter["product_group_id"].map(gi).to_numpy()
    X[rows, cols] = inter["weight"].to_numpy()

    # ── Leave-one-out evaluation ────────────────────────────────────────────
    # Hold out a RANDOM interacted group per customer (taste is stable, not
    # sequential, so a random hold-out isolates personalisation better than a
    # most-recent hold-out, which is biased toward end-of-window seasonal items).
    n_groups = inter.groupby("customer_id")["product_group_id"].transform("size")
    held = inter[n_groups >= 2].groupby("customer_id", group_keys=False).sample(
        n=1, random_state=M.SEED)
    train = X.copy()
    for _, r in held.iterrows():
        train[cu[r["customer_id"]], gi[r["product_group_id"]]] = 0.0

    scores_tr = _cf_scores(train)
    pop = train.sum(axis=0)                       # popularity baseline (col sums)

    cf_hits = base_hits = 0
    for _, r in held.iterrows():
        ci, target = cu[r["customer_id"]], gi[r["product_group_id"]]
        seen = train[ci] > 0
        cand = np.where(~seen)[0]
        cf_top = cand[np.argsort(scores_tr[ci, cand])[::-1][:EVAL_K]]
        base_top = cand[np.argsort(pop[cand])[::-1][:EVAL_K]]
        cf_hits += target in cf_top
        base_hits += target in base_top
    n_eval = len(held)
    print(f"\nHold-out ({n_eval:,} customers), hit-rate@{EVAL_K}:")
    print(f"  CF (item-based kNN)  : {cf_hits / n_eval:.3f}  "
          f"(precision@{EVAL_K} {cf_hits / (n_eval * EVAL_K):.3f})")
    print(f"  popularity baseline  : {base_hits / n_eval:.3f}")

    # ── Production recommendations (fit on full matrix) ─────────────────────
    scores_full = _cf_scores(X)
    meta = groups_meta.set_index("product_group_id")[["style_name", "category_id"]].to_dict("index")
    recs = []
    for c, ci in cu.items():
        seen = X[ci] > 0
        cand = np.where(~seen)[0]
        top = cand[np.argsort(scores_full[ci, cand])[::-1][:TOP_N]]
        for rank, gidx in enumerate(top, start=1):
            g = groups[gidx]
            recs.append((c, g, meta[g]["style_name"], meta[g]["category_id"],
                         float(scores_full[ci, gidx]), rank))
    recs_df = pd.DataFrame(recs, columns=["customer_id", "product_group_id", "style_name",
                                          "category_id", "score", "rank"])
    M.write_ml_table(con, "cf_recommendations", recs_df)

    M.rule("Example: top CF recommendations for one customer")
    ex = recs_df["customer_id"].iloc[0]
    print(f"  customer {ex}:")
    print(recs_df[recs_df["customer_id"] == ex].head(6)[
        ["style_name", "category_id", "score", "rank"]].to_string(index=False))
    con.close()


if __name__ == "__main__":
    build()
