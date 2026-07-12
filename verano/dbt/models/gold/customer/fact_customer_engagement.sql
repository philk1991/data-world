-- Customer-grain engagement fact: web behaviour (attributed via the EXTENDED
-- identity key for reach) + email engagement. Feeds propensity features in Layer 5.
with sessions as (
    select * from {{ ref('gold_session_summary') }}
),

emails as (
    select * from {{ ref('silver_email__email_events') }}
),

web as (
    select
        customer_id_extended                                   as customer_id,
        count(*)                                               as n_sessions,
        sum(num_events)                                        as n_events,
        sum(num_page_views)                                    as n_page_views,
        sum(num_searches)                                      as n_searches,
        count(*) filter (where is_converted)                   as n_converting_sessions,
        max(session_start)                                     as last_seen_at
    from sessions
    where customer_id_extended is not null
    group by customer_id_extended
),

email_agg as (
    select
        customer_id,
        count(*) filter (where event_type = 'sent')            as emails_sent,
        count(*) filter (where event_type = 'open')            as emails_opened,
        count(*) filter (where event_type = 'click')           as emails_clicked
    from emails
    group by customer_id
)

select
    coalesce(w.customer_id, e.customer_id)                     as customer_id,
    coalesce(w.n_sessions, 0)                                  as n_sessions,
    coalesce(w.n_events, 0)                                    as n_events,
    coalesce(w.n_page_views, 0)                                as n_page_views,
    coalesce(w.n_searches, 0)                                  as n_searches,
    coalesce(w.n_converting_sessions, 0)                       as n_converting_sessions,
    w.last_seen_at,
    coalesce(e.emails_sent, 0)                                 as emails_sent,
    coalesce(e.emails_opened, 0)                               as emails_opened,
    coalesce(e.emails_clicked, 0)                              as emails_clicked,
    round(coalesce(e.emails_opened, 0) / nullif(e.emails_sent, 0), 3)  as email_open_rate,
    round(coalesce(e.emails_clicked, 0) / nullif(e.emails_opened, 0), 3) as email_click_to_open_rate
from web w
full outer join email_agg e on w.customer_id = e.customer_id
