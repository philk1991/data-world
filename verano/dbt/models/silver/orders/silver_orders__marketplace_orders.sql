-- Marketplace (Mirakl) order headers RECONCILED to the first-party order shape.
--
-- This is the reconciliation step: the Mirakl feed uses different column names
-- (mirakl_order_id, customer_ref, created_date, total_price, order_state) and a
-- different status vocabulary. We rename/cast to the conformed schema and map the
-- Mirakl states onto our canonical order_status so gold can UNION both channels
-- into a single fact_order.
with source as (
    select * from {{ source('bronze_orders', 'marketplace_orders') }}
)

select
    mirakl_order_id                      as order_id,
    customer_ref                         as customer_id,        -- may be null (guest)
    created_date::timestamp              as order_at,
    'marketplace'                        as order_channel,
    (customer_ref is null)               as is_guest,
    shop_id                              as seller_id,
    shop_name                            as seller_name,
    total_price::double                  as net_amount,
    commission_rate::double              as commission_rate,
    commission_amount::double            as commission_amount,
    currency_iso_code                    as currency,
    order_state                          as source_order_state,
    -- Map Mirakl states onto the canonical status vocabulary.
    case
        when order_state in ('SHIPPED', 'RECEIVED', 'CLOSED')     then 'completed'
        when order_state in ('SHIPPING', 'WAITING_ACCEPTANCE')    then 'in_progress'
        when order_state in ('CANCELED', 'REFUSED')               then 'cancelled'
        else 'unknown'
    end                                  as order_status,
    ingested_at::timestamp               as ingested_at
from source
