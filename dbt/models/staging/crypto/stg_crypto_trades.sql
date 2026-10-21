WITH source AS (
    SELECT *
    FROM
        {{ source('raw_crypto', 'raw_trades') }}
)

SELECT
    trade_id,
    symbol,
    price,
    quantity,
    price * quantity AS notional_value,
    buyer_maker,
    trade_time::TIMESTAMPTZ AS trade_time,
    event_time::TIMESTAMPTZ AS event_time,
    consumed_at::TIMESTAMPTZ AS consumed_at
FROM
    source
