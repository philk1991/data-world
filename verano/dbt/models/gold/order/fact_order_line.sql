-- Conformed order-line fact: first-party + marketplace lines UNIONed. Marketplace
-- lines don't carry a category, so we join dim_product to fill it in.
with first_party as (
    select * from {{ ref('silver_orders__order_lines') }}
),

marketplace as (
    select * from {{ ref('silver_orders__marketplace_order_lines') }}
),

variants as (
    select variant_id, category_id from {{ ref('dim_product') }}
)

select
    line_id,
    order_id,
    variant_id,
    category_id,
    quantity,
    unit_price,
    line_amount,
    is_returned,
    return_reason,
    'first_party'                        as order_channel
from first_party

union all

select
    m.line_id,
    m.order_id,
    m.variant_id,
    v.category_id,
    m.quantity,
    m.unit_price,
    m.line_amount,
    m.is_returned,
    m.return_reason,
    'marketplace'                        as order_channel
from marketplace m
left join variants v using (variant_id)
