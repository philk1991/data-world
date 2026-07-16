"""/website/recommendations/{customer_id} — PDP / homepage pull.

  homepage : the customer's blended ranked_recommendations; cold-start customers
             (unknown, or no recs) fall back to popularity.
  pdp      : "customers also bought" — co-purchase neighbours of the viewed product.
"""
from __future__ import annotations

import duckdb
from fastapi import APIRouter, Depends, Query

from dependencies import db

router = APIRouter(prefix="/website", tags=["website"])


def _popularity_fallback(con, limit: int) -> dict:
    rows = con.execute("""
        select variant_id, style_name, category_id, price
        from ml.popularity_scores
        where is_in_stock
        order by popularity_score desc limit ?
    """, [limit]).df()
    return {"source": "popularity_fallback", "personalized": False,
            "items": rows.to_dict("records")}


@router.get("/recommendations/{customer_id}")
def recommendations(
    customer_id: str,
    slot: str = Query("homepage", pattern="^(homepage|pdp)$"),
    product_id: str | None = None,
    limit: int = 10,
    con: duckdb.DuckDBPyConnection = Depends(db),
) -> dict:
    # PDP slot: co-purchase neighbours of the viewed product.
    if slot == "pdp" and product_id:
        grp = con.execute(
            "select product_group_id from gold.dim_product where variant_id = ?", [product_id]).fetchone()
        if grp:
            rows = con.execute("""
                select cp.neighbour_style_name as style_name,
                       cp.neighbour_category_id as category_id, cp.score,
                       v.variant_id, v.price
                from ml.item_co_purchase cp
                left join gold.dim_product v
                       on v.product_group_id = cp.neighbour_product_group_id
                      and v.is_in_stock and v.is_active
                where cp.product_group_id = ?
                qualify row_number() over (partition by cp.neighbour_product_group_id order by cp.rank) = 1
                order by cp.rank limit ?
            """, [grp[0], limit]).df()
            if not rows.empty:
                return {"customer_id": customer_id, "slot": "pdp", "source": "co_purchase",
                        "personalized": False, "items": rows.to_dict("records")}
        return {"customer_id": customer_id, "slot": "pdp", **_popularity_fallback(con, limit)}

    # Homepage slot: the customer's blended ranked recommendations.
    rows = con.execute("""
        select variant_id, style_name, category_id, size, price, final_score, rank
        from ml.ranked_recommendations
        where customer_id = ?
        order by rank limit ?
    """, [customer_id, limit]).df()
    if not rows.empty:
        return {"customer_id": customer_id, "slot": "homepage", "source": "ranking",
                "personalized": True, "items": rows.to_dict("records")}

    # Cold start: unknown customer or no recommendations yet.
    return {"customer_id": customer_id, "slot": "homepage", **_popularity_fallback(con, limit)}
