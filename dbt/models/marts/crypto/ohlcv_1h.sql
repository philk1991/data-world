-- 1-hour OHLCV candles rolled up from 1-minute candles.
-- Incremental: each run processes only candles newer than the latest hour candle.
{{
    config(
        materialized='incremental',
        unique_key=['symbol', 'candle_open_time'],
        on_schema_change='sync_all_columns'
    )
}}

with candles_1m as (
    select * from {{ ref('ohlcv_1m') }}
    {% if is_incremental() %}
    where candle_open_time > (select max(candle_open_time) from {{ this }})
    {% endif %}
)

select
    symbol,
    date_trunc('hour', candle_open_time)    as candle_open_time,
    min_by(open, candle_open_time)          as open,
    max(high)                               as high,
    min(low)                                as low,
    max_by(close, candle_open_time)         as close,
    sum(volume)                             as volume,
    sum(notional_volume)                    as notional_volume,
    sum(trade_count)                        as trade_count
from candles_1m
group by symbol, date_trunc('hour', candle_open_time)
order by symbol, candle_open_time
