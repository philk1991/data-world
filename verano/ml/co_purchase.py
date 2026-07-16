"""Module 2 — Item-item co-purchase ("customers also bought").

Co-occurrence at PRODUCT-GROUP grain (size/colour variants would fragment the
signal). Evidence is combined from two sources, since same-basket pairs alone are
sparse in this dataset:
  * same basket        — items bought together in one order   (weight 2.0)
  * same customer      — items bought by one customer over time (weight 1.0)
Similarity is cosine over the weighted co-occurrence. Top-N neighbours per group
are written out for the "also bought" serving slot.

    task verano:ml:copurchase
"""
from __future__ import annotations

import itertools
from collections import defaultdict

import pandas as pd

import mlbase as M

TOP_N = 10
MIN_COOC = 2.0          # ignore pairs seen less than this (noise floor)
W_BASKET = 2.0
W_CUSTOMER = 1.0


def build() -> None:
    con = M.connect()

    lines = con.execute("""
        select fol.order_id, fo.customer_id, p.product_group_id
        from gold.fact_order_line fol
        join gold.fact_order fo using (order_id)
        left join gold.dim_product p on fol.variant_id = p.variant_id
        where p.product_group_id is not null
    """).df()

    groups = con.execute("""
        select distinct product_group_id, style_name, category_id
        from gold.dim_product
    """).df()
    meta = groups.set_index("product_group_id")[["style_name", "category_id"]].to_dict("index")

    # Build the weighted transaction list: baskets + per-customer group sets.
    transactions: list[tuple[set[str], float]] = []
    for _, grp in lines.groupby("order_id"):
        s = set(grp["product_group_id"])
        if len(s) >= 2:
            transactions.append((s, W_BASKET))
    for cust, grp in lines[lines["customer_id"].notna()].groupby("customer_id"):
        s = set(grp["product_group_id"])
        if len(s) >= 2:
            transactions.append((s, W_CUSTOMER))

    # Weighted occurrence + co-occurrence.
    occ: dict[str, float] = defaultdict(float)
    cooc: dict[tuple[str, str], float] = defaultdict(float)
    for s, w in transactions:
        for g in s:
            occ[g] += w
        for a, b in itertools.combinations(sorted(s), 2):
            cooc[(a, b)] += w

    # Cosine similarity, emitted symmetrically.
    rows = []
    for (a, b), c in cooc.items():
        if c < MIN_COOC:
            continue
        sim = c / (occ[a] * occ[b]) ** 0.5
        rows.append((a, b, c, sim))
        rows.append((b, a, c, sim))

    pairs = pd.DataFrame(rows, columns=["product_group_id", "neighbour_product_group_id",
                                        "cooc_weight", "score"])
    pairs["rank"] = pairs.groupby("product_group_id")["score"].rank(ascending=False, method="first")
    pairs = pairs[pairs["rank"] <= TOP_N].sort_values(["product_group_id", "rank"])

    # Attach readable names/categories.
    pairs["style_name"] = pairs["product_group_id"].map(lambda g: meta.get(g, {}).get("style_name"))
    pairs["category_id"] = pairs["product_group_id"].map(lambda g: meta.get(g, {}).get("category_id"))
    pairs["neighbour_style_name"] = pairs["neighbour_product_group_id"].map(lambda g: meta.get(g, {}).get("style_name"))
    pairs["neighbour_category_id"] = pairs["neighbour_product_group_id"].map(lambda g: meta.get(g, {}).get("category_id"))
    pairs["rank"] = pairs["rank"].astype(int)

    M.write_ml_table(con, "item_co_purchase", pairs[[
        "product_group_id", "style_name", "category_id",
        "neighbour_product_group_id", "neighbour_style_name", "neighbour_category_id",
        "cooc_weight", "score", "rank"]])

    M.rule("Sanity: 'customers also bought' for a sample dress / occasionwear style")
    for cat in ("dresses", "occasionwear", "knitwear"):
        seed = pairs[pairs["category_id"] == cat]
        if seed.empty:
            continue
        gid = seed.iloc[0]["product_group_id"]
        top = seed[seed["product_group_id"] == gid].head(5)
        print(f"\n  {top.iloc[0]['style_name']} ({cat}) →")
        for _, r in top.iterrows():
            print(f"    {r['neighbour_style_name']:<28} [{r['neighbour_category_id']:<13}] "
                  f"score={r['score']:.3f}")
    con.close()


if __name__ == "__main__":
    build()
