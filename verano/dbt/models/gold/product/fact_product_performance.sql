-- Product performance at variant grain: browsing funnel + sales + returns.
-- dim_product is the spine so every variant appears (even zero-traffic ones).
with products as (
    select * from {{ ref('dim_product') }}
),

events as (
    select * from {{ ref('silver_events__events') }}
),

lines as (
    select * from {{ ref('fact_order_line') }}
),

-- Browsing funnel counts per variant.
funnel as (
    select
        product_id                                             as variant_id,
        count(*) filter (where event_type = 'page_view' and page_type = 'pdp') as view_count,
        count(*) filter (where event_type = 'add_to_cart')     as add_to_cart_count,
        count(*) filter (where event_type = 'purchase')        as purchase_event_count
    from events
    where product_id is not null
    group by product_id
),

-- Sales + returns per variant.
sales as (
    select
        variant_id,
        sum(quantity)                                          as units_sold,
        sum(line_amount)                                       as gross_revenue,
        sum(case when is_returned then line_amount else 0 end) as returned_revenue,
        count(*) filter (where is_returned)                    as return_count,
        count(*)                                               as line_count
    from lines
    group by variant_id
)

select
    p.variant_id,
    p.product_group_id,
    p.style_name,
    p.category_id,
    p.brand_line,
    p.price,
    p.is_in_stock,
    coalesce(f.view_count, 0)                                  as view_count,
    coalesce(f.add_to_cart_count, 0)                           as add_to_cart_count,
    coalesce(s.units_sold, 0)                                  as units_sold,
    coalesce(s.gross_revenue, 0)                               as gross_revenue,
    coalesce(s.gross_revenue, 0) - coalesce(s.returned_revenue, 0) as net_revenue,
    coalesce(s.return_count, 0)                                as return_count,
    round(coalesce(s.return_count, 0) / nullif(s.line_count, 0), 3) as return_rate,
    round(coalesce(f.purchase_event_count, 0) / nullif(f.view_count, 0), 4) as view_to_purchase_rate
from products p
left join funnel f using (variant_id)
left join sales s using (variant_id)
