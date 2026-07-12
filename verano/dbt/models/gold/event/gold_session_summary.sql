-- One row per session: funnel metrics + duration + the resolved customer and
-- resolution tier. The business-facing session mart.
with sessions as (
    select * from {{ ref('silver_events__sessions') }}
),

resolution as (
    select session_id, customer_id_strict, customer_id_extended,
           resolution_tier, resolution_confidence
    from {{ ref('identity_graph') }}
)

select
    s.session_id,
    s.anonymous_id,
    s.session_start,
    s.session_end,
    date_diff('second', s.session_start, s.session_end)        as duration_seconds,
    s.num_events,
    s.num_page_views,
    s.num_searches,
    s.num_add_to_cart,
    s.num_purchases,
    s.is_identified,
    s.is_converted,
    s.device_type,
    s.traffic_source,
    r.customer_id_strict,
    r.customer_id_extended,
    r.resolution_tier,
    r.resolution_confidence
from sessions s
left join resolution r using (session_id)
