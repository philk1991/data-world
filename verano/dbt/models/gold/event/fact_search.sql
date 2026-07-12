-- fact_search: search events with the resolved customer attached. Searches carry
-- only an anonymous_id, so we resolve at cookie grain from the bridge (best
-- deterministic, else best probabilistic). Ground-truth column dropped.
with searches as (
    select * from {{ ref('silver_search__search_logs') }}
),

cookie_resolution as (
    select
        anonymous_id,
        max(customer_id) filter (where confidence_tier = 'deterministic') as customer_id_strict,
        coalesce(
            max(customer_id) filter (where confidence_tier = 'deterministic'),
            max(customer_id) filter (where confidence_tier = 'probabilistic')
        )                                                                  as customer_id_extended
    from {{ ref('bridge_identity') }}
    group by anonymous_id
)

select
    s.search_id,
    s.event_at,
    s.anonymous_id,
    cr.customer_id_strict,
    cr.customer_id_extended,
    s.query_text,
    s.category_id,
    s.results_count,
    s.clicked_position,
    s.clicked_product_id,
    s.converted
from searches s
left join cookie_resolution cr using (anonymous_id)
