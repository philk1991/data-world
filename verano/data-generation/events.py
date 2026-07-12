"""Clickstream event generator — the core of the synthetic dataset.

Produces raw-grain web events (page_view, search, add_to_cart, purchase, plus the
identity-signal events login / email_click / loyalty_signup). The design goals:

  * Most traffic is anonymous. Only *known customers* can trip a deterministic
    identity signal, and only in some sessions — so the identification rate stays
    realistically low.
  * Every event carries a hidden ``_true_customer_id`` and ``_true_session_id``
    (underscore-prefixed) that the resolution logic must NOT use — they exist so
    Stage 3 can measure identity precision/recall and sessionization accuracy.
  * ``customer_id`` is populated ONLY on the deterministic-signal events (login,
    email_click, loyalty_signup, checkout purchase). Everything else is null, so
    resolving a browsing session to a customer is a genuine join problem.
  * Cookie churn + shared household IPs create the *probabilistic* signals
    (persistent cookie, IP+user-agent) that Stage 3 keeps in a separate tier.
  * Seasonal category weighting + a pre-Christmas traffic curve create visible
    spikes (occasionwear in December). Cross-sell adds a learnable co-purchase
    signal.

Returns three DataFrames: events, purchases (one row per purchased line, consumed
by orders.py), and searches (consumed by search.py).
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

import config as C

MARKETPLACE_SELLERS = [
    ("SHOP-101", "Aster Boutique"), ("SHOP-102", "The Occasion Co"),
    ("SHOP-103", "Petite Edit"), ("SHOP-104", "Luxe Accessories"),
    ("SHOP-105", "Northern Knits"),
]

# Monthly overall-traffic curve (pre-Christmas peak, January sales bump).
_TRAFFIC_MONTH_WEIGHT = {11: 1.3, 12: 1.5, 1: 1.1, 2: 0.9, 3: 0.95, 4: 0.9}


def _window_months() -> list[tuple[int, int]]:
    """List of (year, month) tuples spanned by the window."""
    months, cur = [], pd.Timestamp(C.WINDOW_START).replace(day=1)
    end = pd.Timestamp(C.WINDOW_END)
    while cur <= end:
        months.append((cur.year, cur.month))
        cur = (cur + pd.offsets.MonthBegin(1))
    return months


def _rand_ip(rng: np.random.Generator) -> str:
    return f"81.{int(rng.integers(0,256))}.{int(rng.integers(0,256))}.{int(rng.integers(1,255))}"


def _build_variant_index(variants: pd.DataFrame):
    """cat_id -> {size -> [variant dicts]} plus cat_id -> [variant dicts]."""
    cat_size: dict[str, dict[str, list[dict]]] = {}
    cat_all: dict[str, list[dict]] = {}
    for v in variants.to_dict("records"):
        cat_all.setdefault(v["category_id"], []).append(v)
        cat_size.setdefault(v["category_id"], {}).setdefault(v["size"], []).append(v)
    return cat_all, cat_size


def _session_datetime(rng: np.random.Generator, months: list[tuple[int, int]],
                      month_p: np.ndarray) -> pd.Timestamp:
    """Sample a session start, weighted toward the pre-Christmas peak, evening-heavy."""
    yi = int(rng.choice(len(months), p=month_p))
    year, month = months[yi]
    start = pd.Timestamp(year=year, month=month, day=1)
    month_end = start + pd.offsets.MonthEnd(1)
    lo = max(start, pd.Timestamp(C.WINDOW_START))
    hi = min(month_end, pd.Timestamp(C.WINDOW_END))
    day = lo + timedelta(days=int(rng.integers(0, max((hi - lo).days, 1))))
    # Hour weighted to lunchtime + evening browsing.
    hours = np.arange(24)
    hw = np.array([0.2 if 1 <= h <= 6 else (1.6 if h in (12, 13, 20, 21, 22) else 1.0) for h in hours])
    hour = int(rng.choice(hours, p=hw / hw.sum()))
    return day.replace(hour=hour, minute=int(rng.integers(0, 60)), second=int(rng.integers(0, 60)))


def _pick_variant(rng, cat_id, home_size, cat_all, cat_size, filter_size: bool):
    """Choose a variant in a category, optionally biased to the customer's size."""
    size_map = cat_size.get(cat_id, {})
    if filter_size and home_size in size_map:
        pool, used_size = size_map[home_size], home_size
    else:
        pool = cat_all.get(cat_id, [])
        used_size = None
    if not pool:
        return None, None
    return pool[int(rng.integers(len(pool)))], used_size


def _build_query(rng, cat_noun_by_id, cat_id, home_size, brand) -> str:
    """A fashion-flavoured free-text search query."""
    parts = []
    if rng.random() < 0.4:
        parts.append(str(rng.choice(C.COLOURS)).lower())
    if brand == "Petite" and rng.random() < 0.6:
        parts.append("petite")
    parts.append(str(rng.choice(cat_noun_by_id[cat_id])).lower())
    if rng.random() < 0.25:
        parts.append(f"size {home_size}")
    return " ".join(parts)


def build_events(rng: np.random.Generator, customers_current: pd.DataFrame,
                 variants: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cat_all, cat_size = _build_variant_index(variants)
    leaf_categories = list(cat_all.keys())
    months = _window_months()
    month_p = np.array([_TRAFFIC_MONTH_WEIGHT.get(m, 1.0) for _, m in months])
    month_p = month_p / month_p.sum()

    # Per-category seasonal weights precomputed per month for fast category choice.
    seasonal_by_month = {
        m: np.array([C.seasonal_weight(c, m) for c in leaf_categories]) for _, m in months
    }

    events, purchases, searches = [], [], []
    evt_n = ses_n = order_n = search_n = 0

    # ── Assemble the visitor population ──────────────────────────────────────
    visitors = []
    cust = customers_current.to_dict("records")
    for c in cust:
        if rng.random() < C.P_CUSTOMER_ACTIVE:
            n_sessions = 1 + int(rng.poisson(C.MEAN_SESSIONS_KNOWN))
            visitors.append(dict(true_id=c["customer_id"], known=True, email=c["email"],
                                 home_size=c["home_size"], brand=c["brand_line_affinity"],
                                 prefers_petite=c["prefers_petite"],
                                 loyalty_member=c["loyalty_member"],
                                 fav_category=str(rng.choice(leaf_categories)),
                                 n_sessions=n_sessions))
    for i in range(C.N_ANON_VISITORS):
        n_sessions = 1 + int(rng.poisson(C.MEAN_SESSIONS_ANON))
        visitors.append(dict(true_id=f"V{i:06d}", known=False, email=None,
                             home_size=str(rng.choice(C.SIZES_STANDARD)),
                             brand=str(rng.choice(C.BRAND_LINES)), prefers_petite=False,
                             loyalty_member=False,
                             fav_category=str(rng.choice(leaf_categories)),
                             n_sessions=n_sessions))

    # Shared household IP pool (a few visitors collide on these — probabilistic noise).
    household_ips = [_rand_ip(rng) for _ in range(400)]

    def category_weights(month, fav):
        w = seasonal_by_month[month].copy()
        w[leaf_categories.index(fav)] *= 2.5  # visitors browse their favourite consistently
        return w / w.sum()

    # ── Generate sessions ────────────────────────────────────────────────────
    for vis in visitors:
        # Devices: 1, plus maybe a second (own cookie / UA / IP).
        n_devices = 2 if rng.random() < C.P_SECOND_DEVICE else 1
        devices = []
        for _ in range(n_devices):
            dtype = str(rng.choice(C.DEVICE_TYPES, p=C.DEVICE_WEIGHTS))
            devices.append(dict(
                device_type=dtype,
                user_agent=str(rng.choice(C.USER_AGENTS[dtype])),
                base_ip=_rand_ip(rng),
                cookie=f"anon_{rng.integers(1<<62):016x}",
            ))

        for _ in range(vis["n_sessions"]):
            dev = devices[int(rng.integers(len(devices)))]
            # Cookie churn -> a fresh anonymous_id for this session.
            if rng.random() < C.P_COOKIE_RESET:
                dev["cookie"] = f"anon_{rng.integers(1<<62):016x}"
            anon_id = dev["cookie"]
            ip = (household_ips[int(rng.integers(len(household_ips)))]
                  if rng.random() < C.P_SHARED_HOUSEHOLD_IP else dev["base_ip"])

            ses_n += 1
            session_id = f"S{ses_n:07d}"
            t = _session_datetime(rng, months, month_p)
            month = t.month
            cat_p = category_weights(month, vis["fav_category"])
            source = str(rng.choice(C.TRAFFIC_SOURCES, p=C.TRAFFIC_SOURCE_WEIGHTS))

            # Decide deterministic signals up front (known customers only).
            email_sourced = vis["known"] and (source == "email" or rng.random() < C.P_EMAIL_SOURCED)
            will_login = vis["known"] and rng.random() < C.P_LOGIN
            will_loyalty = vis["known"] and vis["loyalty_member"] and rng.random() < C.P_LOYALTY_SIGNUP

            def base_event(**kw):
                nonlocal evt_n
                evt_n += 1
                row = dict(
                    event_id=f"E{evt_n:08d}", event_at=kw["at"], event_type=kw["etype"],
                    anonymous_id=anon_id, customer_id=kw.get("customer_id"),
                    page_type=kw.get("page_type"), product_id=kw.get("product_id"),
                    category_id=kw.get("category_id"), brand_line=kw.get("brand_line"),
                    search_query=kw.get("search_query"), filter_size=kw.get("filter_size"),
                    filter_colour=kw.get("filter_colour"), order_id=kw.get("order_id"),
                    quantity=kw.get("quantity"), unit_price=kw.get("unit_price"),
                    is_marketplace=kw.get("is_marketplace"), seller_id=kw.get("seller_id"),
                    device_type=dev["device_type"], user_agent=dev["user_agent"],
                    ip_address=ip, traffic_source=source,
                    _true_customer_id=vis["true_id"], _true_session_id=session_id,
                )
                events.append(row)

            at = t
            def step():
                nonlocal at
                at = at + timedelta(seconds=int(rng.integers(8, 200)))
                return at

            # Entry event.
            if email_sourced:
                promo, _ = _pick_variant(rng, str(rng.choice(leaf_categories, p=cat_p)),
                                         vis["home_size"], cat_all, cat_size, False)
                base_event(at=at, etype="email_click", page_type="email_landing",
                           customer_id=vis["true_id"],
                           product_id=promo["variant_id"] if promo else None,
                           category_id=promo["category_id"] if promo else None,
                           brand_line=promo["brand_line"] if promo else None)
            else:
                base_event(at=at, etype="page_view",
                           page_type=str(rng.choice(["home", "plp", "pdp", "search"],
                                                     p=[0.4, 0.3, 0.2, 0.1])))

            if will_login:
                base_event(at=step(), etype="login", page_type="account",
                           customer_id=vis["true_id"])
            if will_loyalty:
                base_event(at=step(), etype="loyalty_signup", page_type="account",
                           customer_id=vis["true_id"])

            # Browsing — a handful of PLP/PDP views, size-filtered for known custs.
            viewed = []  # (variant dict) candidates for cart
            n_views = 1 + int(rng.poisson(3))
            for _ in range(n_views):
                cat_id = str(rng.choice(leaf_categories, p=cat_p))
                filter_size = vis["known"] and rng.random() < C.P_FILTER_TO_HOME_SIZE
                var, used_size = _pick_variant(rng, cat_id, vis["home_size"],
                                               cat_all, cat_size, filter_size)
                if var is None:
                    continue
                if rng.random() < 0.5:  # PLP (browse) view
                    base_event(at=step(), etype="page_view", page_type="plp",
                               category_id=cat_id, brand_line=var["brand_line"],
                               filter_size=used_size,
                               filter_colour=str(rng.choice(C.COLOURS)) if rng.random() < 0.3 else None)
                else:  # PDP (product) view
                    base_event(at=step(), etype="page_view", page_type="pdp",
                               product_id=var["variant_id"], category_id=cat_id,
                               brand_line=var["brand_line"])
                    viewed.append(var)

            # Search.
            if rng.random() < C.P_SEARCH:
                cat_id = str(rng.choice(leaf_categories, p=cat_p))
                query = _build_query(rng, C.CATEGORY_NOUNS, cat_id, vis["home_size"], vis["brand"])
                results_count = int(rng.integers(0, 120))
                clicked_var, _ = _pick_variant(rng, cat_id, vis["home_size"], cat_all, cat_size, False)
                clicked = clicked_var is not None and results_count > 0 and rng.random() < 0.45
                s_at = step()
                base_event(at=s_at, etype="search", page_type="search",
                           search_query=query, category_id=cat_id,
                           product_id=clicked_var["variant_id"] if clicked else None)
                if clicked:
                    viewed.append(clicked_var)
                search_n += 1
                searches.append(dict(
                    search_id=f"Q{search_n:07d}", event_at=s_at, anonymous_id=anon_id,
                    customer_id=vis["true_id"] if (will_login or email_sourced) else None,
                    query_text=query, category_id=cat_id, results_count=results_count,
                    clicked_position=int(rng.integers(1, min(results_count, 20) + 1)) if clicked else None,
                    clicked_product_id=clicked_var["variant_id"] if clicked else None,
                    converted=bool(clicked and rng.random() < 0.3),
                    _true_customer_id=vis["true_id"],
                ))

            # Cart + conversion.
            if viewed and rng.random() < C.P_ADD_TO_CART:
                basket = [viewed[int(rng.integers(len(viewed)))]]
                base_event(at=step(), etype="add_to_cart", page_type="pdp",
                           product_id=basket[0]["variant_id"],
                           category_id=basket[0]["category_id"], brand_line=basket[0]["brand_line"],
                           quantity=1)

                if rng.random() < C.P_PURCHASE_GIVEN_CART:
                    # Cross-sell: add a commercially sensible complementary item.
                    seed_cat = basket[0]["category_id"]
                    if seed_cat in C.COMPLEMENTS and rng.random() < C.P_CROSS_SELL:
                        comp_cat = str(rng.choice(C.COMPLEMENTS[seed_cat]))
                        comp, _ = _pick_variant(rng, comp_cat, vis["home_size"], cat_all, cat_size, False)
                        if comp is not None:
                            basket.append(comp)

                    order_n += 1
                    order_id = f"O{order_n:07d}"
                    is_mkt = rng.random() < C.P_MARKETPLACE_ORDER
                    seller = MARKETPLACE_SELLERS[int(rng.integers(len(MARKETPLACE_SELLERS)))] if is_mkt else (None, None)
                    # Known customers are identified at checkout (email capture).
                    cust_id = vis["true_id"] if vis["known"] else None
                    for line_var in basket:
                        qty = 1 + int(rng.random() < 0.15)
                        p_at = step()
                        base_event(at=p_at, etype="purchase", page_type="checkout",
                                   product_id=line_var["variant_id"], category_id=line_var["category_id"],
                                   brand_line=line_var["brand_line"], customer_id=cust_id,
                                   order_id=order_id, quantity=qty, unit_price=line_var["price"],
                                   is_marketplace=is_mkt, seller_id=seller[0])
                        purchases.append(dict(
                            order_id=order_id, customer_id=cust_id, order_at=p_at,
                            variant_id=line_var["variant_id"], category_id=line_var["category_id"],
                            brand_line=line_var["brand_line"], quantity=qty,
                            unit_price=line_var["price"], is_marketplace=is_mkt,
                            seller_id=seller[0], seller_name=seller[1], anonymous_id=anon_id,
                        ))

    events_df = pd.DataFrame(events)
    purchases_df = pd.DataFrame(purchases)
    searches_df = pd.DataFrame(searches)
    return events_df, purchases_df, searches_df
