with source as (
    select * from {{ source('raw_payments', 'raw_requests') }}
)

select
    payment_id,
    amount,
    requested_at::timestamptz as requested_at,
    consumed_at::timestamptz  as consumed_at
from source
qualify row_number() over (partition by payment_id order by consumed_at) = 1
