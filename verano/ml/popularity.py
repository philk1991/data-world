"""Module 1 — Popularity / trending.

The cold-start fallback: needs no customer identity. Scores every variant by recent
demand (weighted views + purchases) and a trend score (recent window vs the prior
window). Used directly by serving when we know nothing about a visitor.

    task verano:ml:popularity
"""
from __future__ import annotations

import mlbase as M


def build() -> None:
    con = M.connect()

    # Anchor the windows to the latest event in the data.
    max_at = con.execute("SELECT max(event_at) FROM gold.fact_event").fetchone()[0]
    print(f"Popularity anchored at {max_at:%Y-%m-%d} (recent = trailing 30d, prior = 30–60d)")

    # Per-variant demand + recent/prior split, joined to the product dimension.
    scores = con.execute("""
        with events as (
            select product_id as variant_id, event_type, event_at
            from gold.fact_event
            where product_id is not null
        ),
        agg as (
            select
                variant_id,
                count(*) filter (where event_type = 'page_view')                   as views_all,
                count(*) filter (where event_type = 'purchase')                    as purchases_all,
                count(*) filter (where event_at >  $max_at - interval 30 day)      as demand_recent,
                count(*) filter (where event_at <= $max_at - interval 30 day
                                   and event_at >  $max_at - interval 60 day)      as demand_prior
            from events
            group by variant_id
        )
        select
            p.variant_id, p.product_group_id, p.style_name, p.category_id,
            p.brand_line, p.price, p.is_in_stock,
            coalesce(a.views_all, 0)      as views_all,
            coalesce(a.purchases_all, 0)  as purchases_all,
            coalesce(a.demand_recent, 0)  as demand_recent,
            coalesce(a.demand_prior, 0)   as demand_prior
        from gold.dim_product p
        left join agg a using (variant_id)
    """, {"max_at": max_at}).df()

    # Popularity = purchases weighted above views. Trend = recent vs prior lift.
    scores["popularity_score"] = 5.0 * scores["purchases_all"] + 1.0 * scores["views_all"]
    scores["trend_score"] = (scores["demand_recent"] + 1) / (scores["demand_prior"] + 1)

    scores["rank_overall"] = scores["popularity_score"].rank(ascending=False, method="first").astype(int)
    scores["rank_in_category"] = (
        scores.groupby("category_id")["popularity_score"]
              .rank(ascending=False, method="first").astype(int)
    )
    scores = scores.sort_values("rank_overall").reset_index(drop=True)

    M.write_ml_table(con, "popularity_scores", scores)

    M.rule("Top 10 overall (cold-start fallback — no customer needed)")
    print(scores.head(10)[["style_name", "category_id", "brand_line",
                           "purchases_all", "views_all", "trend_score"]].to_string(index=False))

    M.rule("Top trending (biggest recent-vs-prior lift, min 15 recent events)")
    trend = scores[scores["demand_recent"] >= 15].sort_values("trend_score", ascending=False)
    print(trend.head(8)[["style_name", "category_id", "demand_recent", "demand_prior",
                         "trend_score"]].to_string(index=False))
    con.close()


if __name__ == "__main__":
    build()
