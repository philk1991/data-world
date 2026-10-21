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

WITH trades AS (
    SELECT *
    FROM
        {{ ref('stg_crypto_trades') }}
    {% if is_incremental() %}
    WHERE
        trade_time > (
            SELECT MAX(candle_open_time)
            FROM
                {{ this }}
        )
    {% endif %}
)

SELECT
    symbol,
    DATE_TRUNC('minute', trade_time) AS candle_open_time,
    MIN_BY(price, trade_time) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    MAX_BY(price, trade_time) AS close,
    SUM(quantity) AS volume,
    SUM(notional_value) AS notional_volume,
    COUNT(*) AS trade_count
FROM
    trades
GROUP BY
    symbol, DATE_TRUNC('minute', trade_time)
ORDER BY
    symbol, candle_open_time
