WITH source AS (
    SELECT *
    FROM
        {{ source('raw_payments', 'raw_rejections') }}
)

SELECT
    payment_id,
    rejected_at::TIMESTAMPTZ AS rejected_at,
    consumed_at::TIMESTAMPTZ AS consumed_at
FROM
    source
QUALIFY ROW_NUMBER() OVER (PARTITION BY payment_id ORDER BY consumed_at) = 1
