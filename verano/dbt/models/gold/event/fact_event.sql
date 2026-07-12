-- fact_event: the assembled event-level view. Every event is joined (via its
-- session) to the identity graph, so browsing events carry the resolved customer
-- keys (strict + extended). Raw PII (ip_address, user_agent) and the ground-truth
-- _true_* columns are dropped here — gold is production-facing.
with events as (
    select * from {{ ref('silver_events__events') }}
),

resolution as (
    select session_id, customer_id_strict, customer_id_extended, resolution_tier
    from {{ ref('identity_graph') }}
)

select
    e.event_id,
    e.event_at,
    e.event_type,
    e.anonymous_id,
    e.session_id,
    r.customer_id_strict,
    r.customer_id_extended,
    r.resolution_tier,
    e.page_type,
    e.product_id,
    e.category_id,
    e.brand_line,
    e.search_query,
    e.filter_size,
    e.filter_colour,
    e.order_id,
    e.quantity,
    e.unit_price,
    e.is_marketplace,
    e.seller_id,
    e.device_type,
    e.traffic_source
from events e
left join resolution r using (session_id)
