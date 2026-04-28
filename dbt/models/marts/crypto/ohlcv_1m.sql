-- 1-minute OHLCV candles per trading pair.
-- Incremental: each run processes only trades newer than the latest candle.
-- min_by/max_by give the price at the earliest/latest trade_time in the window.
{{
    config(
        materialized='incremental',
        unique_key=['symbol', 'candle_open_time'],
        on_schema_change='sync_all_columns'
    )
}}

with trades as (
    select * from {{ ref('stg_crypto_trades') }}
    {% if is_incremental() %}
    where trade_time > (select max(candle_open_time) from {{ this }})
    {% endif %}
)

select
    symbol,
    date_trunc('minute', trade_time)        as candle_open_time,
    min_by(price, trade_time)               as open,
    max(price)                              as high,
    min(price)                              as low,
    max_by(price, trade_time)               as close,
    sum(quantity)                           as volume,
    sum(notional_value)                     as notional_volume,
    count(*)                                as trade_count
from trades
group by symbol, date_trunc('minute', trade_time)
order by symbol, candle_open_time
