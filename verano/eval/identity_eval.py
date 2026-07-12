"""Evaluate identity resolution against the hidden ground truth.

Every event carries a hidden _true_customer_id that the resolution logic never
reads. This script scores the bridge and the identity graph against it, so you
can quote concrete precision/recall/coverage numbers in the panel — and show the
precision↔recall trade-off between the strict (deterministic) and extended
(deterministic + probabilistic) resolution keys.

    task verano:identity:eval
"""
from __future__ import annotations

import os
import sys

import duckdb

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data-generation"))
import config as C  # noqa: E402


def _rule(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


def main() -> None:
    con = duckdb.connect(C.DUCKDB_PATH, read_only=True)

    # Ground truth: each cookie belongs to exactly one true visitor. A visitor id
    # starting with 'C' is a real customer; 'V' is an anonymous-only visitor who
    # can NEVER be correctly resolved to a customer (any link to them is wrong).
    con.execute("""
        CREATE OR REPLACE TEMP VIEW cookie_truth AS
        SELECT DISTINCT anonymous_id, _true_customer_id AS true_id
        FROM silver_events.silver_events__events
    """)

    _rule("Bridge composition (links by tier and method)")
    print(con.execute("""
        SELECT confidence_tier, link_method, count(*) AS links, round(avg(confidence),2) AS conf
        FROM identity.bridge_identity
        GROUP BY 1,2 ORDER BY 1 DESC, links DESC
    """).df().to_string(index=False))

    _rule("Link precision by method (link correct if customer_id == cookie's true customer)")
    print(con.execute("""
        SELECT b.confidence_tier, b.link_method,
               count(*) AS links,
               sum(CASE WHEN b.customer_id = t.true_id THEN 1 ELSE 0 END) AS correct,
               round(100.0*sum(CASE WHEN b.customer_id = t.true_id THEN 1 ELSE 0 END)/count(*),1) AS precision_pct
        FROM identity.bridge_identity b
        JOIN cookie_truth t USING (anonymous_id)
        GROUP BY 1,2 ORDER BY 1 DESC, links DESC
    """).df().to_string(index=False))

    _rule("Session resolution coverage (all sessions)")
    print(con.execute("""
        SELECT resolution_tier, count(*) AS sessions,
               round(100.0*count(*)/sum(count(*)) OVER (),1) AS pct
        FROM identity.identity_graph
        GROUP BY 1 ORDER BY sessions DESC
    """).df().to_string(index=False))

    # Precision/recall on sessions whose TRUE identity is a real customer.
    _rule("Strict vs extended key — precision/recall on known-customer sessions")
    print(con.execute("""
        WITH g AS (
            SELECT *, (_true_customer_id LIKE 'C%') AS true_is_customer
            FROM identity.identity_graph
        ),
        known AS (SELECT count(*) AS n FROM g WHERE true_is_customer)
        SELECT 'strict (deterministic)' AS key,
               count(*) FILTER (WHERE customer_id_strict IS NOT NULL) AS resolved,
               sum(CASE WHEN customer_id_strict = _true_customer_id THEN 1 ELSE 0 END) AS correct,
               round(100.0*sum(CASE WHEN customer_id_strict = _true_customer_id THEN 1 ELSE 0 END)
                     / nullif(count(*) FILTER (WHERE customer_id_strict IS NOT NULL),0),1) AS precision_pct,
               round(100.0*sum(CASE WHEN customer_id_strict = _true_customer_id THEN 1 ELSE 0 END)
                     / (SELECT n FROM known),1) AS recall_pct
        FROM g
        UNION ALL
        SELECT 'extended (det+prob)' AS key,
               count(*) FILTER (WHERE customer_id_extended IS NOT NULL) AS resolved,
               sum(CASE WHEN customer_id_extended = _true_customer_id THEN 1 ELSE 0 END) AS correct,
               round(100.0*sum(CASE WHEN customer_id_extended = _true_customer_id THEN 1 ELSE 0 END)
                     / nullif(count(*) FILTER (WHERE customer_id_extended IS NOT NULL),0),1) AS precision_pct,
               round(100.0*sum(CASE WHEN customer_id_extended = _true_customer_id THEN 1 ELSE 0 END)
                     / (SELECT n FROM known),1) AS recall_pct
        FROM g
    """).df().to_string(index=False))

    print("\n\033[2mReading: the strict key trades recall for near-perfect precision;\n"
          "the extended key lifts recall by adding probabilistic links, at some precision cost.\033[0m")
    con.close()


if __name__ == "__main__":
    main()
