-- First-party order headers, typed.
with source as (
    select * from {{ source('bronze_orders', 'orders') }}
)

select
    order_id,
    customer_id,
    order_at::timestamp                  as order_at,
    order_channel,
    is_guest::boolean                    as is_guest,
    num_lines::int                       as num_lines,
    num_units::int                       as num_units,
    gross_amount::double                 as gross_amount,
    discount_amount::double              as discount_amount,
    net_amount::double                   as net_amount,
    order_status,
    ingested_at::timestamp               as ingested_at
from source
