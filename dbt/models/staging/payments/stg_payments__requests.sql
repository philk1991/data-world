WITH source AS (
    SELECT *
    FROM
        {{ source('raw_payments', 'raw_requests') }}
)

SELECT
    payment_id,
    amount,
    requested_at::TIMESTAMPTZ AS requested_at,
    consumed_at::TIMESTAMPTZ AS consumed_at
FROM
    source
QUALIFY ROW_NUMBER() OVER (PARTITION BY payment_id ORDER BY consumed_at) = 1
