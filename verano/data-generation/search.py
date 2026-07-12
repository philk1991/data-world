"""Search-log assembly.

The rich search rows are emitted alongside the clickstream in events.py (so the
query text, click position and conversion stay consistent with the matching
search event). This module just finalises the bronze_search schema and column
order — kept as its own step to mirror the per-domain generator layout.
"""
from __future__ import annotations

import pandas as pd

_COLUMNS = ["search_id", "event_at", "anonymous_id", "customer_id", "query_text",
            "category_id", "results_count", "clicked_position", "clicked_product_id",
            "converted", "_true_customer_id"]


def build_search_logs(searches: pd.DataFrame) -> pd.DataFrame:
    return searches.reindex(columns=_COLUMNS)
