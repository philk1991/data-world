"""/email/batch-export — batch propensity + recommendation export for a campaign.

The batch/reverse-ETL pattern: pull the highest-propensity customers and their top
product recommendations for a CRM send. Crucially, the export is GATED ON CONSENT —
only customers whose current (SCD) marketing_consent is true are included. This is
the governance point: personalisation must respect consent at activation time.
"""
from __future__ import annotations

import duckdb
from fastapi import APIRouter, Depends, Query

from dependencies import db

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/batch-export")
def batch_export(
    campaign: str = "reactivation",
    limit: int = 100,
    min_decile: int = Query(1, ge=1, le=10),
    recs_per_customer: int = 3,
    con: duckdb.DuckDBPyConnection = Depends(db),
) -> dict:
    # Consent-gated audience, ranked by propensity.
    audience = con.execute("""
        select p.customer_id, c.email, c.first_name,
               round(p.purchase_propensity, 4) as propensity, p.propensity_decile
        from ml.propensity_scores p
        join gold.gold_customer_360 c using (customer_id)
        where c.marketing_consent = true
          and p.propensity_decile >= ?
        order by p.purchase_propensity desc
        limit ?
    """, [min_decile, limit]).df()

    if audience.empty:
        return {"campaign": campaign, "consent_gated": True, "count": 0, "recipients": []}

    ids = audience["customer_id"].tolist()
    recs = con.execute("""
        select customer_id, style_name, category_id, variant_id, price, rank
        from ml.ranked_recommendations
        where customer_id in ({}) and rank <= ?
        order by customer_id, rank
    """.format(",".join(["?"] * len(ids))), [*ids, recs_per_customer]).df()
    recs_by_cust = {c: g[["style_name", "category_id", "variant_id", "price"]].to_dict("records")
                    for c, g in recs.groupby("customer_id")}

    recipients = [{
        "customer_id": r.customer_id, "email": r.email, "first_name": r.first_name,
        "propensity": float(r.propensity), "propensity_decile": int(r.propensity_decile),
        "recommendations": recs_by_cust.get(r.customer_id, []),
    } for r in audience.itertuples(index=False)]

    return {
        "campaign": campaign,
        "consent_gated": True,
        "min_decile": min_decile,
        "count": len(recipients),
        "recipients": recipients,
    }
