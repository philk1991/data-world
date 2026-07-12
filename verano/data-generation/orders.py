"""Order generator — first-party orders plus a Mirakl-style marketplace variant.

Consumes the purchase lines emitted by events.py and assembles four tables:
  - orders / order_lines                       : first-party (native schema)
  - marketplace_orders / marketplace_order_lines : Mirakl-style feed

The marketplace feed deliberately uses a DIFFERENT schema and status vocabulary
(mirakl_order_id, shop_id, customer_ref, order_state, commission_amount, ...),
so Stage 2 has a real reconciliation/conforming job: unioning both into a single
fact_order with an order_channel. Returns are concentrated in fit/occasion
categories (occasionwear, denim) via config.RETURN_RATE.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

import config as C

_MIRAKL_STATES = ["SHIPPED", "RECEIVED", "CLOSED", "SHIPPING", "WAITING_ACCEPTANCE",
                  "CANCELED", "REFUSED"]
_MIRAKL_STATE_P = [0.28, 0.34, 0.22, 0.08, 0.03, 0.03, 0.02]
_DISCOUNT_RATES = [0.0, 0.10, 0.20]
_DISCOUNT_P = [0.6, 0.28, 0.12]


def _returned(rng, cat_id) -> tuple[bool, str | None]:
    if rng.random() < C.RETURN_RATE.get(cat_id, 0.10):
        return True, str(rng.choice(C.RETURN_REASONS))
    return False, None


def build_orders(rng: np.random.Generator, purchases: pd.DataFrame):
    """Return (orders_df, order_lines_df, mkt_orders_df, mkt_lines_df)."""
    orders, order_lines = [], []
    mkt_orders, mkt_lines = [], []

    for order_id, grp in purchases.groupby("order_id", sort=False):
        rows = grp.to_dict("records")
        head = rows[0]
        order_at = pd.Timestamp(min(r["order_at"] for r in rows))
        gross = float(sum(r["quantity"] * r["unit_price"] for r in rows))
        discount_rate = float(rng.choice(_DISCOUNT_RATES, p=_DISCOUNT_P))
        discount = round(gross * discount_rate, 2)
        net = round(gross - discount, 2)
        num_units = int(sum(r["quantity"] for r in rows))

        if head["is_marketplace"]:
            mirakl_id = f"MIR-{order_id}"
            commission_rate = round(float(rng.uniform(0.10, 0.20)), 3)
            mkt_orders.append(dict(
                mirakl_order_id=mirakl_id, shop_id=head["seller_id"], shop_name=head["seller_name"],
                customer_ref=head["customer_id"],  # may be null (guest)
                created_date=order_at.strftime("%Y-%m-%d"),
                order_state=str(rng.choice(_MIRAKL_STATES, p=_MIRAKL_STATE_P)),
                total_price=net, currency_iso_code="GBP",
                commission_rate=commission_rate,
                commission_amount=round(net * commission_rate, 2),
            ))
            for j, r in enumerate(rows, start=1):
                is_ret, reason = _returned(rng, r["category_id"])
                mkt_lines.append(dict(
                    mirakl_order_id=mirakl_id, mirakl_line_id=f"{mirakl_id}-{j}",
                    offer_sku=r["variant_id"], quantity=int(r["quantity"]),
                    price_unit=float(r["unit_price"]),
                    line_total=round(r["quantity"] * r["unit_price"], 2),
                    is_refunded=is_ret, refund_reason=reason,
                ))
        else:
            orders.append(dict(
                order_id=order_id, customer_id=head["customer_id"], order_at=order_at,
                order_channel="first_party", is_guest=head["customer_id"] is None,
                num_lines=len(rows), num_units=num_units,
                gross_amount=round(gross, 2), discount_amount=discount, net_amount=net,
                order_status=str(rng.choice(["completed", "cancelled"], p=[0.97, 0.03])),
            ))
            for j, r in enumerate(rows, start=1):
                is_ret, reason = _returned(rng, r["category_id"])
                returned_at = order_at + timedelta(days=int(rng.integers(5, 30))) if is_ret else None
                order_lines.append(dict(
                    order_id=order_id, line_id=f"{order_id}-{j}", variant_id=r["variant_id"],
                    category_id=r["category_id"], quantity=int(r["quantity"]),
                    unit_price=float(r["unit_price"]),
                    line_amount=round(r["quantity"] * r["unit_price"], 2),
                    is_returned=is_ret, return_reason=reason, returned_at=returned_at,
                ))

    return (pd.DataFrame(orders), pd.DataFrame(order_lines),
            pd.DataFrame(mkt_orders), pd.DataFrame(mkt_lines))
