-- First-party order lines, typed, with return flags.
with source as (
    select * from {{ source('bronze_orders', 'order_lines') }}
)

select
    line_id,
    order_id,
    variant_id,
    category_id,
    quantity::int                        as quantity,
    unit_price::double                   as unit_price,
    line_amount::double                  as line_amount,
    is_returned::boolean                 as is_returned,
    return_reason,
    returned_at::timestamp               as returned_at,
    ingested_at::timestamp               as ingested_at
from source
