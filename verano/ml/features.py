"""Shared feature builder for propensity (and reusable elsewhere).

Builds POINT-IN-TIME customer features as of a cutoff timestamp — only data
strictly before the cutoff is used, so there is no label leakage. This is why
propensity can't just read gold_customer_360 (whose RFM is computed over all time).
"""
from __future__ import annotations

import pandas as pd

import mlbase as M


def build_features(con, cutoff: pd.Timestamp) -> pd.DataFrame:
    """One row per identified customer with RFM + engagement features as of `cutoff`."""
    # Web behaviour (attributed via the extended identity key) before the cutoff.
    web = con.execute("""
        select
            customer_id_extended as customer_id,
            count(distinct session_id)                          as n_sessions,
            count(*)                                            as n_events,
            count(*) filter (where event_type = 'page_view')    as n_page_views,
            count(*) filter (where event_type = 'search')       as n_searches,
            count(*) filter (where event_type = 'add_to_cart')  as n_add_to_cart,
            max(event_at)                                       as last_event_at
        from gold.fact_event
        where customer_id_extended is not null and event_at < $cutoff
        group by 1
    """, {"cutoff": cutoff}).df()

    # Orders (RFM) before the cutoff.
    orders = con.execute("""
        select
            customer_id,
            count(*)                as n_orders,
            sum(net_amount)         as total_spend,
            max(order_at)           as last_order_at
        from gold.fact_order
        where customer_id is not null and order_status <> 'cancelled' and order_at < $cutoff
        group by 1
    """, {"cutoff": cutoff}).df()

    # Email engagement before the cutoff.
    email = con.execute("""
        select
            customer_id,
            count(*) filter (where event_type = 'open')   as emails_opened,
            count(*) filter (where event_type = 'click')  as emails_clicked
        from silver_email.silver_email__email_events
        where event_at < $cutoff
        group by 1
    """, {"cutoff": cutoff}).df()

    # Stable customer attributes (low leakage) from the current dimension.
    attrs = con.execute("""
        select customer_id, loyalty_member, loyalty_tier, brand_line_affinity
        from gold.dim_customer where is_current
    """).df()

    df = (web.merge(orders, on="customer_id", how="outer")
             .merge(email, on="customer_id", how="outer")
             .merge(attrs, on="customer_id", how="left"))

    # Fill + derive.
    count_cols = ["n_sessions", "n_events", "n_page_views", "n_searches", "n_add_to_cart",
                  "n_orders", "total_spend", "emails_opened", "emails_clicked"]
    df[count_cols] = df[count_cols].fillna(0)
    df["has_prior_order"] = (df["n_orders"] > 0).astype(int)
    df["recency_days"] = (cutoff - pd.to_datetime(df["last_event_at"])).dt.days.fillna(999)
    df["order_recency_days"] = (cutoff - pd.to_datetime(df["last_order_at"])).dt.days.fillna(999)
    df["avg_order_value"] = (df["total_spend"] / df["n_orders"].replace(0, pd.NA)).fillna(0)
    df["loyalty_member"] = df["loyalty_member"].fillna(False).astype(int)
    df["is_gold"] = (df["loyalty_tier"] == "Gold").astype(int)
    df["is_petite"] = (df["brand_line_affinity"] == "Petite").astype(int)

    return df


FEATURE_COLS = [
    "n_sessions", "n_events", "n_page_views", "n_searches", "n_add_to_cart",
    "n_orders", "total_spend", "avg_order_value", "has_prior_order",
    "recency_days", "order_recency_days", "emails_opened", "emails_clicked",
    "loyalty_member", "is_gold", "is_petite",
]
