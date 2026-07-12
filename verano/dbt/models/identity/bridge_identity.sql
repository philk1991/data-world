-- bridge_identity: anonymous_id -> customer_id links.
--
-- The core teaching model. Links are split into two confidence TIERS that are
-- never merged as equal:
--
--   * deterministic  — a trustworthy in-session signal put the customer_id on the
--                      cookie directly: login / loyalty signup / email click with
--                      an encoded id / checkout email capture. Confidence ~1.0.
--                      (A persistent cookie's login identifies ALL of that cookie's
--                      sessions, because the bridge is at cookie grain.)
--   * probabilistic  — the cookie has NO signal of its own, so it is inferred from
--                      a shared device fingerprint (ip + user-agent) or, more
--                      weakly, a shared IP with a deterministically-known cookie.
--                      This is how we recover cookie churn on a known device.
--
-- Downstream (identity_graph) decides which tier to trust. Precision/recall of
-- each tier is measured against the hidden ground truth by the identity eval.
with events as (
    select * from {{ ref('silver_events__events') }}
),

-- ── Deterministic tier ───────────────────────────────────────────────────────
signal_events as (
    select anonymous_id, customer_id, event_type, event_at
    from events
    where customer_id is not null
),

deterministic as (
    select
        anonymous_id,
        customer_id,
        -- strongest signal present on the cookie sets the method + confidence
        case
            when bool_or(event_type in ('login', 'loyalty_signup')) then 'login'
            when bool_or(event_type = 'email_click')                then 'email_click_encoded'
            else 'checkout_email'
        end                                                    as link_method,
        case
            when bool_or(event_type in ('login', 'loyalty_signup')) then 1.00
            when bool_or(event_type = 'email_click')                then 0.99
            else 0.98
        end                                                    as confidence,
        min(event_at)                                          as linked_at,
        count(*)                                               as n_signals
    from signal_events
    group by anonymous_id, customer_id
),

-- ── Probabilistic tier (only cookies with no deterministic link) ─────────────
known_fingerprint as (
    select distinct e.ip_address, e.user_agent, d.customer_id
    from events e
    join deterministic d using (anonymous_id)
),

known_ip as (
    select distinct e.ip_address, d.customer_id
    from events e
    join deterministic d using (anonymous_id)
),

unlinked as (
    select distinct anonymous_id, ip_address, user_agent
    from events
    where anonymous_id not in (select anonymous_id from deterministic)
),

-- Method A: shared device fingerprint (ip + user-agent) — recovers cookie churn.
fp_best as (
    select anonymous_id, customer_id, strength
    from (
        select u.anonymous_id, kf.customer_id, count(*) as strength
        from unlinked u
        join known_fingerprint kf
          on u.ip_address = kf.ip_address and u.user_agent = kf.user_agent
        group by 1, 2
    )
    qualify row_number() over (partition by anonymous_id order by strength desc, customer_id) = 1
),

-- Method B: shared IP only (weaker) — for cookies method A didn't catch.
ip_best as (
    select anonymous_id, customer_id, strength
    from (
        select u.anonymous_id, ki.customer_id, count(*) as strength
        from unlinked u
        join known_ip ki on u.ip_address = ki.ip_address
        where u.anonymous_id not in (select anonymous_id from fp_best)
        group by 1, 2
    )
    qualify row_number() over (partition by anonymous_id order by strength desc, customer_id) = 1
),

probabilistic as (
    select anonymous_id, customer_id, 'device_fingerprint' as link_method,
           0.55 as confidence, strength as n_signals
    from fp_best
    union all
    select anonymous_id, customer_id, 'shared_ip' as link_method,
           0.35 as confidence, strength as n_signals
    from ip_best
)

-- ── Final: one row per (anonymous_id, customer_id, tier) ─────────────────────
select
    anonymous_id,
    customer_id,
    link_method,
    'deterministic'            as confidence_tier,
    confidence,
    linked_at,
    n_signals
from deterministic

union all

select
    anonymous_id,
    customer_id,
    link_method,
    'probabilistic'           as confidence_tier,
    confidence,
    cast(null as timestamp)   as linked_at,
    n_signals
from probabilistic
