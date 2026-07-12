-- Marketplace (Mirakl) order lines reconciled to the first-party line shape.
-- offer_sku -> variant_id, price_unit -> unit_price, is_refunded -> is_returned.
with source as (
    select * from {{ source('bronze_orders', 'marketplace_order_lines') }}
)

select
    mirakl_line_id                       as line_id,
    mirakl_order_id                      as order_id,
    offer_sku                            as variant_id,
    quantity::int                        as quantity,
    price_unit::double                   as unit_price,
    line_total::double                   as line_amount,
    is_refunded::boolean                 as is_returned,
    refund_reason                        as return_reason,
    ingested_at::timestamp               as ingested_at
from source
