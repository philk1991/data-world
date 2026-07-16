"""/search/rerank — simulates the search engine pulling a personalisation score at
query time. Candidates come from a text match over the in-stock catalogue; if the
caller is a known customer we blend in their embedding similarity + CF affinity.
"""
from __future__ import annotations

import duckdb
import numpy as np
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dependencies import customer_context, db, get_store, minmax

router = APIRouter(prefix="/search", tags=["search"])


class RerankRequest(BaseModel):
    query: str
    customer_id: str | None = None
    limit: int = 10


@router.post("/rerank")
def rerank(req: RerankRequest, con: duckdb.DuckDBPyConnection = Depends(db)) -> dict:
    store = get_store()
    cat = store.catalogue

    # Candidate generation: token-overlap relevance over the searchable text.
    tokens = [t for t in req.query.lower().split() if t]
    relevance = cat["search_text"].apply(lambda s: sum(t in s for t in tokens)).to_numpy(float)
    pool = cat[relevance > 0].copy()
    pool["relevance"] = relevance[relevance > 0]
    if pool.empty:                                   # no text match -> whole catalogue
        pool = cat.copy()
        pool["relevance"] = 0.0
    pool = pool.sort_values(["relevance", "popularity"], ascending=False).head(60).reset_index(drop=True)

    # Base score = text relevance + popularity.
    base = 0.6 * minmax(pool["relevance"].to_numpy()) + 0.4 * minmax(pool["popularity"].to_numpy())

    ctx = customer_context(con, req.customer_id) if req.customer_id else None
    home_size = ctx["home_size"] if ctx else None
    personalized = bool(ctx and ctx["embedding"] is not None)
    if personalized:
        cvec = ctx["embedding"]
        emb = pool["product_group_id"].map(
            lambda g: float(cvec @ store.group_emb[g]) if g in store.group_emb else 0.0).to_numpy()
        cf = pool["product_group_id"].map(lambda g: ctx["cf"].get(g, 0.0)).to_numpy()
        personal = 0.6 * minmax(emb) + 0.4 * minmax(cf)
        final = 0.6 * base + 0.4 * personal
    else:
        emb = cf = np.zeros(len(pool))
        final = base

    pool["final"] = final
    # One SKU per style — prefer the customer's size (or one-size accessories).
    pool["size_match"] = (pool["size"] == home_size) | (pool["size"] == "One Size")
    pool = (pool.sort_values(["product_group_id", "size_match", "final"],
                             ascending=[True, False, False])
                .drop_duplicates("product_group_id")
                .sort_values("final", ascending=False)
                .head(req.limit).reset_index(drop=True))

    items = [{
        "variant_id": r.variant_id, "style_name": r.style_name, "category_id": r.category_id,
        "colour": r.colour, "size": r.size, "price": round(float(r.price), 2),
        "score": round(float(r.final), 4),
    } for r in pool.itertuples(index=False)]

    return {
        "query": req.query,
        "customer_id": req.customer_id,
        "personalized": personalized,
        "signal": "embedding + CF blended into relevance" if personalized
                  else "relevance + popularity (no customer context)",
        "results": items,
    }
