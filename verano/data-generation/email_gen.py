"""Email engagement generator.

Produces campaign send/open/click events for marketing-consented customers. The
click rows carry an ``encoded_customer_id`` — the same deterministic identity
signal that email-sourced web sessions expose (an encoded id in the click-through
URL). We don't enforce row-level referential integrity between an email click
here and an email_click web event (they're generated independently); the point is
to model the email channel and its consent gating.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

import config as C

# (name, promoted leaf category, month) — occasion-led campaign calendar.
_CAMPAIGNS = [
    ("November New Season", "knitwear", 11),
    ("Party Season Edit", "occasionwear", 11),
    ("Christmas Gifting", "jewellery", 12),
    ("Occasionwear Countdown", "occasionwear", 12),
    ("January Sale", "denim", 1),
    ("Winter Warmers", "outerwear", 1),
    ("New Year New Dresses", "dresses", 2),
    ("Spring Preview", "dresses", 3),
    ("Spring Occasion", "occasionwear", 4),
]

_P_OPEN = 0.36
_P_CLICK_GIVEN_OPEN = 0.28


def _campaign_send_date(rng, month: int) -> pd.Timestamp:
    year = C.WINDOW_START.year if month >= C.WINDOW_START.month else C.WINDOW_END.year
    base = pd.Timestamp(year=year, month=month, day=int(rng.integers(3, 25)))
    return base.replace(hour=int(rng.integers(7, 11)))


def build_email(rng: np.random.Generator, customers_current: pd.DataFrame,
                variants: pd.DataFrame) -> pd.DataFrame:
    consented = customers_current[customers_current["marketing_consent"]].to_dict("records")
    by_cat = {}
    for v in variants.to_dict("records"):
        by_cat.setdefault(v["category_id"], []).append(v["variant_id"])

    rows = []
    ev_n = 0
    for ci, (name, cat, month) in enumerate(_CAMPAIGNS, start=1):
        campaign_id = f"CMP{ci:03d}"
        send_date = _campaign_send_date(rng, month)
        promo_pool = by_cat.get(cat, [None])
        # Send to a 55–75% sample of consented customers.
        sample_frac = float(rng.uniform(0.55, 0.75))
        for cust in consented:
            if rng.random() > sample_frac:
                continue
            promo = promo_pool[int(rng.integers(len(promo_pool)))]
            ev_n += 1
            rows.append(dict(email_event_id=f"EM{ev_n:08d}", campaign_id=campaign_id,
                             campaign_name=name, customer_id=cust["customer_id"],
                             event_type="sent", event_at=send_date, promoted_product_id=promo,
                             promoted_category=cat, encoded_customer_id=None))
            if rng.random() < _P_OPEN:
                open_at = send_date + timedelta(hours=int(rng.integers(1, 48)))
                ev_n += 1
                rows.append(dict(email_event_id=f"EM{ev_n:08d}", campaign_id=campaign_id,
                                 campaign_name=name, customer_id=cust["customer_id"],
                                 event_type="open", event_at=open_at, promoted_product_id=promo,
                                 promoted_category=cat, encoded_customer_id=None))
                if rng.random() < _P_CLICK_GIVEN_OPEN:
                    click_at = open_at + timedelta(minutes=int(rng.integers(1, 120)))
                    ev_n += 1
                    rows.append(dict(email_event_id=f"EM{ev_n:08d}", campaign_id=campaign_id,
                                     campaign_name=name, customer_id=cust["customer_id"],
                                     event_type="click", event_at=click_at, promoted_product_id=promo,
                                     promoted_category=cat,
                                     encoded_customer_id=cust["customer_id"]))  # deterministic signal
    return pd.DataFrame(rows)
