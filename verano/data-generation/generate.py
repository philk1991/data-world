"""End-to-end synthetic data generation → bronze layer.

Runs every generator with its own deterministic RNG and full-replaces the
bronze_* schemas in verano.duckdb. Idempotent: re-running rebuilds the whole
synthetic history from scratch.

    task verano:gen:all       # or: python generate.py
"""
from __future__ import annotations

import time

import config as C
import writers
import catalogue
import customers
import events
import orders
import search
import email_gen


def main() -> None:
    t0 = time.time()
    print(f"Verano synthetic data generation (seed={C.SEED}, "
          f"window {C.WINDOW_START.date()}..{C.WINDOW_END.date()})")
    print(f"Target: {C.DUCKDB_PATH}\n")

    print("→ catalogue")
    categories, products, variants = catalogue.build_catalogue(C.child_rng("catalogue"))
    print(f"    {len(products):,} product groups → {len(variants):,} variants")

    print("→ customers")
    versions, current = customers.build_customers(C.child_rng("customers"))
    print(f"    {current.shape[0]:,} customers, {len(versions):,} SCD versions")

    print("→ events (clickstream)")
    events_df, purchases_df, searches_df = events.build_events(
        C.child_rng("events"), current, variants)
    print(f"    {len(events_df):,} events, {len(purchases_df):,} purchase lines")

    print("→ orders (first-party + Mirakl marketplace)")
    orders_df, order_lines_df, mkt_orders_df, mkt_lines_df = orders.build_orders(
        C.child_rng("orders"), purchases_df)
    print(f"    {len(orders_df):,} first-party orders, {len(mkt_orders_df):,} marketplace orders")

    print("→ search logs")
    search_logs_df = search.build_search_logs(searches_df)

    print("→ email engagement")
    email_df = email_gen.build_email(C.child_rng("email"), current, variants)
    print(f"    {len(email_df):,} email events\n")

    print("Writing bronze tables:")
    conn = writers.connect(C.DUCKDB_PATH)
    writers.replace_table(conn, "bronze_catalogue", "categories", categories)
    writers.replace_table(conn, "bronze_catalogue", "products", products)
    writers.replace_table(conn, "bronze_catalogue", "product_variants", variants)
    writers.replace_table(conn, "bronze_customers", "customer_versions", versions)
    writers.replace_table(conn, "bronze_events", "events", events_df)
    writers.replace_table(conn, "bronze_orders", "orders", orders_df)
    writers.replace_table(conn, "bronze_orders", "order_lines", order_lines_df)
    writers.replace_table(conn, "bronze_orders", "marketplace_orders", mkt_orders_df)
    writers.replace_table(conn, "bronze_orders", "marketplace_order_lines", mkt_lines_df)
    writers.replace_table(conn, "bronze_search", "search_logs", search_logs_df)
    writers.replace_table(conn, "bronze_email", "email_events", email_df)
    conn.close()

    assert len(events_df) >= C.MIN_EVENTS_TARGET, (
        f"only {len(events_df):,} events generated (< {C.MIN_EVENTS_TARGET:,} target)")
    print(f"\nDone in {time.time() - t0:,.1f}s. "
          f"Run `task verano:gen:profile` to inspect.")


if __name__ == "__main__":
    main()
