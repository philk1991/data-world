"""Sanity-profile the generated bronze data.

Prints the checks you'd eyeball before trusting the dataset: row counts, the
anonymous-vs-identified split, the seasonal occasionwear spike, size-driven
browsing concentration, category return rates and the marketplace share.

    task verano:gen:profile
"""
from __future__ import annotations

import duckdb

import config as C

BRONZE_TABLES = [
    ("bronze_catalogue", "categories"), ("bronze_catalogue", "products"),
    ("bronze_catalogue", "product_variants"), ("bronze_customers", "customer_versions"),
    ("bronze_events", "events"), ("bronze_orders", "orders"),
    ("bronze_orders", "order_lines"), ("bronze_orders", "marketplace_orders"),
    ("bronze_orders", "marketplace_order_lines"), ("bronze_search", "search_logs"),
    ("bronze_email", "email_events"),
]


def _rule(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


def main() -> None:
    con = duckdb.connect(C.DUCKDB_PATH, read_only=True)

    _rule("Row counts")
    for schema, table in BRONZE_TABLES:
        n = con.execute(f"SELECT count(*) FROM {schema}.{table}").fetchone()[0]
        print(f"  {schema}.{table:<26} {n:>9,}")

    _rule("Identity: session identification rate (should be a minority)")
    df = con.execute("""
        WITH sessions AS (
            SELECT _true_session_id,
                   max(CASE WHEN customer_id IS NOT NULL THEN 1 ELSE 0 END) AS identified
            FROM bronze_events.events
            GROUP BY _true_session_id
        )
        SELECT count(*) AS sessions,
               sum(identified) AS identified_sessions,
               round(100.0 * sum(identified) / count(*), 1) AS identified_pct
        FROM sessions
    """).df()
    print(df.to_string(index=False))

    _rule("Seasonality: events per month by category (occasionwear should spike in Dec)")
    df = con.execute("""
        SELECT strftime(event_at, '%Y-%m') AS month,
               sum(CASE WHEN category_id = 'occasionwear' THEN 1 ELSE 0 END) AS occasionwear,
               sum(CASE WHEN category_id = 'knitwear' THEN 1 ELSE 0 END) AS knitwear,
               sum(CASE WHEN category_id = 'dresses' THEN 1 ELSE 0 END) AS dresses,
               count(*) AS all_events
        FROM bronze_events.events
        WHERE category_id IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """).df()
    print(df.to_string(index=False))

    _rule("Size-driven browsing: top filter sizes on PLP views")
    df = con.execute("""
        SELECT filter_size, count(*) AS plp_views
        FROM bronze_events.events
        WHERE page_type = 'plp' AND filter_size IS NOT NULL
        GROUP BY 1 ORDER BY plp_views DESC LIMIT 8
    """).df()
    print(df.to_string(index=False))

    _rule("Returns: return rate by category (occasionwear/denim highest)")
    df = con.execute("""
        SELECT ol.category_id,
               count(*) AS lines,
               round(100.0 * avg(CASE WHEN ol.is_returned THEN 1 ELSE 0 END), 1) AS return_pct
        FROM bronze_orders.order_lines ol
        GROUP BY 1 ORDER BY return_pct DESC
    """).df()
    print(df.to_string(index=False))

    _rule("Marketplace split (first-party vs Mirakl)")
    fp = con.execute("SELECT count(*) FROM bronze_orders.orders").fetchone()[0]
    mk = con.execute("SELECT count(*) FROM bronze_orders.marketplace_orders").fetchone()[0]
    print(f"  first_party={fp:,}  marketplace={mk:,}  "
          f"marketplace_share={100.0 * mk / (fp + mk):.1f}%")

    con.close()


if __name__ == "__main__":
    main()
