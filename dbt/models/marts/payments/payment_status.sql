-- One row per payment with its resolved outcome.
{{
    config(
        materialized='incremental',
        unique_key='payment_id',
        on_schema_change='sync_all_columns'
    )
}}

{% set grace_minutes = 10 %}
{% set lookback_minutes = 20 %}    -- fail safe mechanism

WITH requests AS (
    SELECT *
    FROM
        {{ ref('stg_payments__requests') }}
    {% if is_incremental() %}
    WHERE
        requested_at > (
            SELECT MAX(requested_at) - INTERVAL '{{ lookback_minutes }} minutes'
            FROM
                {{ this }}
        )
    {% endif %}
),

rejections AS (
    SELECT *
    FROM
        {{ ref('stg_payments__rejections') }}
    {% if is_incremental() %}
    -- a rejection relevant to the look-back window has its request within it too
    WHERE
        rejected_at > (
            SELECT MAX(requested_at) - INTERVAL '{{ lookback_minutes }} minutes'
            FROM
                {{ this }}
        )
    {% endif %}
),

-- Transform: attach the rejection (if any), derive status
resolved AS (
    SELECT
        r.payment_id,
        r.amount,
        r.requested_at,
        rej.rejected_at,
        CASE
            WHEN rej.payment_id IS NOT NULL THEN 'rejected'
            WHEN {{ payments_now() }} >= r.requested_at + INTERVAL '{{ grace_minutes }} minutes' THEN 'accepted'
            ELSE 'pending'
        END AS status,
        {{ payments_now() }} AS status_evaluated_at
    FROM
        requests r
    LEFT JOIN
        rejections rej
        USING (payment_id)
)

SELECT *
FROM
    resolved
