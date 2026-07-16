"""Shared serving dependencies — read-only DuckDB access + a small static store.

The API reads the precomputed ml.* tables and gold marts. This is the offline
(dbt + ML) / online (serving) split that stands in for a reverse-ETL push into an
online store: the DuckDB read here is the "online store".

The file is opened READ-ONLY (mirrors the repo's read-only dashboard pattern), so
serving can never contend with dbt / the ML writers. A per-request cursor over one
cached connection keeps concurrent reads thread-safe.
"""
from __future__ import annotations

import functools
import os
import sys

import duckdb
import numpy as np

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data-generation"))
import config as C  # noqa: E402


@functools.lru_cache(maxsize=1)
def _connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(C.DUCKDB_PATH, read_only=True)


def db() -> duckdb.DuckDBPyConnection:
    """FastAPI dependency: a fresh cursor over the shared read-only connection."""
    return _connection().cursor()


class Store:
    """Static lookups loaded once (they don't change while the server runs)."""

    def __init__(self, con: duckdb.DuckDBPyConnection):
        self.catalogue = con.execute("""
            select p.variant_id, p.product_group_id, p.style_name, p.category_id,
                   p.brand_line, p.colour, p.size, p.pattern, p.price,
                   coalesce(ps.popularity_score, 0) as popularity
            from gold.dim_product p
            left join ml.popularity_scores ps using (variant_id)
            where p.is_in_stock and p.is_active
        """).df()
        self.catalogue["search_text"] = (
            self.catalogue["style_name"] + " " + self.catalogue["category_id"] + " "
            + self.catalogue["brand_line"] + " " + self.catalogue["colour"] + " "
            + self.catalogue["pattern"]).str.lower()

        pe = con.execute("select product_group_id, embedding from ml.product_embeddings").df()
        self.group_emb = {g: np.asarray(v, float) for g, v in
                          zip(pe["product_group_id"], pe["embedding"])}


@functools.lru_cache(maxsize=1)
def get_store() -> Store:
    return Store(_connection().cursor())


def customer_context(con: duckdb.DuckDBPyConnection, customer_id: str) -> dict:
    """Per-customer personalisation context; known=False for cold-start customers."""
    prof = con.execute("""
        select home_size, marketing_consent, email
        from gold.gold_customer_360 where customer_id = ?
    """, [customer_id]).fetchone()
    emb = con.execute(
        "select embedding from ml.customer_embeddings where customer_id = ?", [customer_id]).fetchone()
    cf = con.execute(
        "select product_group_id, score from ml.cf_recommendations where customer_id = ?",
        [customer_id]).df()
    prop = con.execute(
        "select purchase_propensity, propensity_decile from ml.propensity_scores where customer_id = ?",
        [customer_id]).fetchone()

    return {
        "known": prof is not None,
        "home_size": prof[0] if prof else None,
        "marketing_consent": bool(prof[1]) if prof else False,
        "email": prof[2] if prof else None,
        "embedding": np.asarray(emb[0], float) if emb else None,
        "cf": dict(zip(cf["product_group_id"], cf["score"])) if not cf.empty else {},
        "propensity": float(prop[0]) if prop else None,
        "propensity_decile": int(prop[1]) if prop else None,
    }


def minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = float(np.min(x)), float(np.max(x))
    if hi <= lo:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)
