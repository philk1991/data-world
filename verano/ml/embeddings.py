"""Module 5 — Product & customer embeddings.

Product embeddings come from the synthetic PDP descriptions; customer embeddings
are the taste-weighted mean of the product groups a customer has browsed. Vectors
are unit-normalised so cosine similarity is a dot product.

Backend (VERANO_EMBEDDINGS): "tfidf" (default — scikit-learn TF-IDF + SVD, no heavy
deps) or "sentence-transformers" (needs torch >= 2.4; unavailable on x86-64 macOS,
so it falls back to tfidf with a warning here).

    task verano:ml:embeddings
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

import mlbase as M

EMB_DIM = 32
BACKEND = os.environ.get("VERANO_EMBEDDINGS", "tfidf")


def _embed_descriptions(texts: list[str]) -> np.ndarray:
    """Return unit-normalised embeddings for a list of product descriptions."""
    if BACKEND == "sentence-transformers":
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            return normalize(model.encode(texts, show_progress_bar=False))
        except Exception as e:  # torch/platform unavailable -> fall back
            print(f"  [warn] sentence-transformers unavailable ({type(e).__name__}); "
                  f"falling back to TF-IDF")
    tfidf = TfidfVectorizer(max_features=400, stop_words="english")
    mat = tfidf.fit_transform(texts)
    svd = TruncatedSVD(n_components=EMB_DIM, random_state=M.SEED)
    return normalize(svd.fit_transform(mat))


def build() -> None:
    con = M.connect()
    print(f"Embeddings backend: {BACKEND}")

    # ── Product embeddings (one per product group) ──────────────────────────
    groups = con.execute("""
        select distinct product_group_id, style_name, category_id, description
        from gold.dim_product order by product_group_id
    """).df()
    vecs = _embed_descriptions(groups["description"].tolist())
    gi = {g: i for i, g in enumerate(groups["product_group_id"])}

    prod = groups[["product_group_id", "style_name", "category_id"]].copy()
    prod["embedding"] = [row.astype(float).tolist() for row in vecs]
    M.write_ml_table(con, "product_embeddings", prod)

    # ── Customer embeddings (taste-weighted mean of browsed groups) ─────────
    inter = con.execute("""
        select customer_id_extended as customer_id, p.product_group_id,
               count(*) as weight
        from gold.fact_event fe
        join gold.dim_product p on fe.product_id = p.variant_id
        where fe.customer_id_extended is not null and fe.product_id is not null
          and fe.event_type in ('page_view', 'add_to_cart')
        group by 1, 2
    """).df()

    cust_rows = []
    for cid, grp in inter.groupby("customer_id"):
        idx = grp["product_group_id"].map(gi).to_numpy()
        w = grp["weight"].to_numpy(float)
        v = (vecs[idx] * w[:, None]).sum(axis=0)
        n = np.linalg.norm(v)
        if n > 0:
            cust_rows.append((cid, (v / n).astype(float).tolist()))
    cust = pd.DataFrame(cust_rows, columns=["customer_id", "embedding"])
    M.write_ml_table(con, "customer_embeddings", cust)

    # ── Sniff test: nearest neighbours of a floral occasion/dress style ─────
    seed_mask = groups["description"].str.contains("floral", case=False) & \
        groups["category_id"].isin(["dresses", "occasionwear"])
    seed_i = int(np.where(seed_mask)[0][0]) if seed_mask.any() else 0
    sims = vecs @ vecs[seed_i]
    order = np.argsort(-sims)[1:6]
    M.rule(f"Nearest neighbours of: {groups.iloc[seed_i]['style_name']} "
           f"[{groups.iloc[seed_i]['category_id']}]")
    for j in order:
        print(f"    {groups.iloc[j]['style_name']:<28} [{groups.iloc[j]['category_id']:<13}] "
              f"cos={sims[j]:.3f}")
    con.close()


if __name__ == "__main__":
    build()
