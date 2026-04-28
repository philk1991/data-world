with source as (
    select * from {{ source('raw_crypto', 'raw_trades') }}
)

select
    trade_id,
    symbol,
    price,
    quantity,
    price * quantity                        as notional_value,
    buyer_maker,
    trade_time::timestamptz                 as trade_time,
    event_time::timestamptz                 as event_time,
    consumed_at::timestamptz                as consumed_at
from source
