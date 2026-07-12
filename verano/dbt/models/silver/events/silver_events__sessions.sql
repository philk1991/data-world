-- One row per derived session, with funnel counts and the in-session
-- deterministic customer id (if the visitor tripped a signal). This is the grain
-- identity resolution and session analytics build on.
with events as (
    select * from {{ ref('silver_events__events') }}
)

select
    session_id,
    anonymous_id,
    min(event_at)                                                as session_start,
    max(event_at)                                                as session_end,
    count(*)                                                     as num_events,
    count(*) filter (where event_type = 'page_view')            as num_page_views,
    count(*) filter (where event_type = 'search')               as num_searches,
    count(*) filter (where event_type = 'add_to_cart')          as num_add_to_cart,
    count(*) filter (where event_type = 'purchase')             as num_purchases,
    max(customer_id)                                            as session_customer_id,  -- deterministic in-session id
    (max(case when customer_id is not null then 1 else 0 end) = 1) as is_identified,
    (max(case when event_type = 'purchase' then 1 else 0 end) = 1) as is_converted,
    any_value(device_type)                                     as device_type,
    any_value(traffic_source)                                  as traffic_source,
    -- evaluation-only ground truth
    any_value(_true_customer_id)                               as _true_customer_id,
    any_value(_true_session_id)                                as _true_session_id
from events
group by session_id, anonymous_id
