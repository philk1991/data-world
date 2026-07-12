-- Conformed order fact: first-party + Mirakl marketplace UNIONed into one grain.
-- This is where the reconciliation pays off — both channels share order_channel,
-- net_amount, order_status and (for marketplace) seller_id + commission_amount.
with first_party as (
    select * from {{ ref('silver_orders__orders') }}
),

marketplace as (
    select * from {{ ref('silver_orders__marketplace_orders') }}
)

select
    order_id,
    customer_id,
    order_at,
    order_channel,
    is_guest,
    net_amount,
    order_status,
    cast(null as varchar)                as seller_id,
    0.0                                  as commission_amount
from first_party

union all

select
    order_id,
    customer_id,
    order_at,
    order_channel,
    is_guest,
    net_amount,
    order_status,
    seller_id,
    commission_amount
from marketplace
