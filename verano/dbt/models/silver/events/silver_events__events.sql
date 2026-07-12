-- Cleaned, typed clickstream with a derived session_id.
--
-- Sessionization: standard 30-minute inactivity rule. Events are ordered within
-- an anonymous_id; a gap > 30 minutes starts a new session. session_seq is a
-- running count of session starts per cookie, so session_id is unique globally.
--
-- _true_customer_id / _true_session_id are carried through for EVALUATION ONLY
-- (Stage 3 scores identity + sessionization against them); production logic must
-- never read them.
with source as (
    select * from {{ source('bronze_events', 'events') }}
),

cleaned as (
    select
        event_id,
        event_at::timestamp                  as event_at,
        event_type,
        anonymous_id,
        customer_id,
        page_type,
        product_id,
        category_id,
        brand_line,
        search_query,
        filter_size,
        filter_colour,
        order_id,
        quantity::int                        as quantity,
        unit_price::double                   as unit_price,
        is_marketplace::boolean              as is_marketplace,
        seller_id,
        device_type,
        user_agent,
        ip_address,
        traffic_source,
        _true_customer_id,
        _true_session_id,
        ingested_at::timestamp               as ingested_at
    from source
),

flagged as (
    select
        *,
        case
            when lag(event_at) over w is null
              or event_at - lag(event_at) over w > interval 30 minute
            then 1 else 0
        end as is_new_session
    from cleaned
    window w as (partition by anonymous_id order by event_at, event_id)
),

sessionised as (
    select
        *,
        sum(is_new_session) over (
            partition by anonymous_id order by event_at, event_id
            rows between unbounded preceding and current row
        ) as session_seq
    from flagged
)

select
    * exclude (is_new_session, session_seq),
    anonymous_id || '-s' || lpad(session_seq::varchar, 5, '0') as session_id
from sessionised
