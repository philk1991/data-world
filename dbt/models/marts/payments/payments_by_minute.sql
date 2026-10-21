-- Bucket size is set by the `payments_bucket_minutes` var (1 or 5) via the bucket_timestamp macro. 
-- Incremental with a look-back window, so recent buckets are recomputed as their payments settle.
{{
    config(
        materialized='incremental',
        unique_key='request_bucket',
        on_schema_change='sync_all_columns'
    )
}}

{% set lookback_minutes = 20 %}

WITH status AS (
    SELECT *
    FROM
        {{ ref('payment_status') }}
    {% if is_incremental() %}
    WHERE
        requested_at > (
            SELECT MAX(request_bucket) - INTERVAL '{{ lookback_minutes }} minutes'
            FROM
                {{ this }}
        )
    {% endif %}
),

by_bucket AS (
    SELECT
        {{ bucket_timestamp('requested_at') }} AS request_bucket,
        COUNT(*) AS payments_total,
        COUNT(*) FILTER (WHERE status = 'accepted') AS payments_accepted,
        COUNT(*) FILTER (WHERE status = 'rejected') AS payments_rejected,
        COUNT(*) FILTER (WHERE status = 'pending') AS payments_pending,
        SUM(amount) AS amount_total,
        SUM(amount) FILTER (WHERE status = 'accepted') AS amount_accepted,
        SUM(amount) FILTER (WHERE status = 'rejected') AS amount_rejected,
        SUM(amount) FILTER (WHERE status = 'pending') AS amount_pending,
        NOW() AS refreshed_at
    FROM
        status
    GROUP BY
        request_bucket
)

SELECT *
FROM
    by_bucket
ORDER BY
    request_bucket
