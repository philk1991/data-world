"""Customer / CRM / loyalty generator, with an SCD-friendly change history.

Emits ``customer_versions``: one row per (customer, version). Most customers have
a single version; a realistic minority change over the window — withdrawing email
consent, upgrading loyalty tier, changing size or moving region. gold builds a
Type-2 slowly-changing dimension from these versions (valid_from/valid_to), which
is the identity/consent-history teaching point. (In production you'd let dbt
snapshots capture this incrementally; a versions table reproduces the same shape
deterministically in a single run.)

Also returns a ``current`` view (latest version per customer) used to drive event
generation — the browsing behaviour needs each customer's home size, brand
affinity and loyalty status.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

import config as C

# Size popularity — peaks around a UK 12–14.
_SIZE_WEIGHTS = np.array([0.08, 0.16, 0.22, 0.21, 0.15, 0.11, 0.07])


def _random_signup(rng: np.random.Generator) -> pd.Timestamp:
    """A signup date up to ~3 years before the window end."""
    days_before = int(rng.integers(30, 3 * 365))
    return pd.Timestamp(C.WINDOW_END) - timedelta(days=days_before)


def build_customers(rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (versions_df, current_df)."""
    versions = []

    for i in range(1, C.N_CUSTOMERS + 1):
        customer_id = f"C{i:06d}"
        first = str(rng.choice(C.FIRST_NAMES))
        last = str(rng.choice(C.LAST_NAMES))
        email = f"{first}.{last}{i}@example.com".lower()
        brand_affinity = str(rng.choice(C.BRAND_LINES, p=C.BRAND_LINE_WEIGHTS))
        home_size = str(rng.choice(C.SIZES_STANDARD, p=_SIZE_WEIGHTS))
        prefers_petite = brand_affinity == "Petite"
        region = str(rng.choice(C.UK_REGIONS))
        postcode_area = str(rng.choice(C.POSTCODE_AREAS))
        signup = _random_signup(rng)

        loyalty_member = bool(rng.random() < 0.42)
        tier = str(rng.choice(["Bronze", "Silver", "Gold"], p=[0.55, 0.30, 0.15])) if loyalty_member else None

        # Consent flags. Most opt into email at signup; a data-processing consent
        # is near-universal (needed to hold the account).
        email_consent = bool(rng.random() < 0.68)
        marketing_consent = email_consent and bool(rng.random() < 0.85)
        data_processing_consent = bool(rng.random() < 0.98)

        # Version 1 — established at signup.
        state = dict(
            customer_id=customer_id, first_name=first, last_name=last, email=email,
            brand_line_affinity=brand_affinity, home_size=home_size, prefers_petite=prefers_petite,
            region=region, postcode_area=postcode_area, signup_date=signup.date(),
            loyalty_member=loyalty_member, loyalty_tier=tier,
            email_consent=email_consent, marketing_consent=marketing_consent,
            data_processing_consent=data_processing_consent,
        )
        versions.append({**state, "version_number": 1,
                         "effective_at": pd.Timestamp(signup),
                         "change_reason": "signup"})

        # A minority change during the window -> extra SCD versions.
        n_changes = int(rng.choice([0, 1, 2], p=[0.82, 0.15, 0.03]))
        last_effective = pd.Timestamp(signup)
        for v in range(2, 2 + n_changes):
            # Change lands somewhere inside the observation window.
            eff = pd.Timestamp(C.WINDOW_START) + timedelta(
                days=int(rng.integers(0, max(C.window_days(), 1))))
            if eff <= last_effective:
                eff = last_effective + timedelta(days=1)
            last_effective = eff

            change = str(rng.choice(
                ["consent_withdrawal", "loyalty_upgrade", "size_change", "region_move"],
                p=[0.40, 0.25, 0.20, 0.15]))
            state = {**state}  # copy previous state, then mutate one facet
            if change == "consent_withdrawal":
                state["email_consent"] = False
                state["marketing_consent"] = False
            elif change == "loyalty_upgrade":
                state["loyalty_member"] = True
                order = ["Bronze", "Silver", "Gold"]
                cur = state["loyalty_tier"] or "Bronze"
                state["loyalty_tier"] = order[min(order.index(cur) + 1, 2)]
            elif change == "size_change":
                state["home_size"] = str(rng.choice(C.SIZES_STANDARD, p=_SIZE_WEIGHTS))
            elif change == "region_move":
                state["region"] = str(rng.choice(C.UK_REGIONS))
                state["postcode_area"] = str(rng.choice(C.POSTCODE_AREAS))

            versions.append({**state, "version_number": v,
                             "effective_at": eff, "change_reason": change})

    versions_df = pd.DataFrame(versions)

    # Current view = latest version per customer.
    current_df = (versions_df.sort_values(["customer_id", "version_number"])
                             .groupby("customer_id", as_index=False).tail(1)
                             .reset_index(drop=True))

    return versions_df, current_df
