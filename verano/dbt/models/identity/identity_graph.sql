-- identity_graph: resolve each SESSION to a customer, exposing TWO keys so
-- downstream consumers pick their own risk appetite:
--
--   * customer_id_strict   — deterministic links only (high precision, lower recall)
--   * customer_id_extended — deterministic first, else probabilistic (higher recall,
--                            some precision traded away)
--
-- Consumers that must not misattribute (e.g. GDPR-sensitive personalisation) use
-- the strict key; recall-hungry use cases (e.g. broad re-targeting) can opt into
-- the extended key knowing it carries probabilistic links. _true_customer_id is
-- carried for evaluation only.
with sessions as (
    select * from {{ ref('silver_events__sessions') }}
),

bridge as (
    select * from {{ ref('bridge_identity') }}
),

-- Best deterministic and best probabilistic link per cookie.
det as (
    select anonymous_id, customer_id, confidence, link_method
    from bridge
    where confidence_tier = 'deterministic'
    qualify row_number() over (partition by anonymous_id order by confidence desc) = 1
),

prob as (
    select anonymous_id, customer_id, confidence, link_method
    from bridge
    where confidence_tier = 'probabilistic'
    qualify row_number() over (partition by anonymous_id order by confidence desc) = 1
)

select
    s.session_id,
    s.anonymous_id,
    s.session_start,
    s.num_events,
    s.is_converted,
    det.customer_id                                            as customer_id_strict,
    coalesce(det.customer_id, prob.customer_id)                as customer_id_extended,
    case
        when det.customer_id is not null  then 'deterministic'
        when prob.customer_id is not null then 'probabilistic'
        else 'unresolved'
    end                                                        as resolution_tier,
    coalesce(det.link_method, prob.link_method)                as resolution_method,
    coalesce(det.confidence, prob.confidence)                  as resolution_confidence,
    s._true_customer_id
from sessions s
left join det  on s.anonymous_id = det.anonymous_id
left join prob on s.anonymous_id = prob.anonymous_id
