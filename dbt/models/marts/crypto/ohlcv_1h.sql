-- 1-hour OHLCV candles rolled up from 1-minute candles.
-- Incremental: each run processes only candles newer than the latest hour candle.
{{
    config(
        materialized='incremental',
        unique_key=['symbol', 'candle_open_time'],
        on_schema_change='sync_all_columns'
    )
}}

WITH candles_1m AS (
    SELECT *
    FROM
        {{ ref('ohlcv_1m') }}
    {% if is_incremental() %}
    WHERE
        candle_open_time > (
            SELECT MAX(candle_open_time)
            FROM
                {{ this }}
        )
    {% endif %}
)

SELECT
    symbol,
    DATE_TRUNC('hour', candle_open_time) AS candle_open_time,
    MIN_BY(open, candle_open_time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    MAX_BY(close, candle_open_time) AS close,
    SUM(volume) AS volume,
    SUM(notional_volume) AS notional_volume,
    SUM(trade_count) AS trade_count
FROM
    candles_1m
GROUP BY
    symbol, DATE_TRUNC('hour', candle_open_time)
ORDER BY
    symbol, candle_open_time
