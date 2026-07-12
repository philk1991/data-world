-- gold_customer_360: the assembled, one-row-per-customer view joining the current
-- customer attributes, order value/RFM, returns and engagement. The presentation
-- mart that serving and the ML feature builders read from.
with customers as (
    select * from {{ ref('dim_customer') }} where is_current
),

orders as (
    select * from {{ ref('fact_order') }}
),

lines as (
    select * from {{ ref('fact_order_line') }}
),

engagement as (
    select * from {{ ref('fact_customer_engagement') }}
),

-- Dataset "now" = latest order timestamp, for recency.
as_of as (
    select max(order_at) as now_at from orders
),

order_agg as (
    select
        customer_id,
        count(*)                                               as n_orders,
        sum(net_amount)                                        as total_net_spend,
        avg(net_amount)                                        as avg_order_value,
        min(order_at)                                          as first_order_at,
        max(order_at)                                          as last_order_at
    from orders
    where customer_id is not null
      and order_status <> 'cancelled'
    group by customer_id
),

return_agg as (
    select
        o.customer_id,
        count(*) filter (where l.is_returned)                  as n_returned_lines,
        count(*)                                               as n_lines
    from lines l
    join orders o using (order_id)
    where o.customer_id is not null
    group by o.customer_id
)

select
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    c.brand_line_affinity,
    c.home_size,
    c.region,
    c.loyalty_member,
    c.loyalty_tier,
    c.email_consent,
    c.marketing_consent,
    coalesce(o.n_orders, 0)                                    as n_orders,
    coalesce(o.total_net_spend, 0)                             as total_net_spend,
    round(o.avg_order_value, 2)                                as avg_order_value,
    o.first_order_at,
    o.last_order_at,
    date_diff('day', o.last_order_at, (select now_at from as_of)) as recency_days,
    coalesce(r.n_returned_lines, 0)                            as n_returned_lines,
    round(coalesce(r.n_returned_lines, 0) / nullif(r.n_lines, 0), 3) as return_rate,
    coalesce(e.n_sessions, 0)                                  as n_sessions,
    coalesce(e.n_events, 0)                                    as n_events,
    coalesce(e.emails_opened, 0)                               as emails_opened,
    coalesce(e.emails_clicked, 0)                              as emails_clicked,
    -- Coarse lifecycle stage for cold-start / propensity segmentation.
    case
        when o.n_orders is null                                                       then 'prospect'
        when date_diff('day', o.last_order_at, (select now_at from as_of)) <= 60       then 'active'
        else 'lapsing'
    end                                                        as lifecycle_stage
from customers c
left join order_agg o using (customer_id)
left join return_agg r using (customer_id)
left join engagement e using (customer_id)
