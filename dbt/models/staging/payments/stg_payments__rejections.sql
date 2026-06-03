with source as (
    select * from {{ source('raw_payments', 'raw_rejections') }}
)

select
    payment_id,
    rejected_at::timestamptz as rejected_at,
    consumed_at::timestamptz as consumed_at
from source
qualify row_number() over (partition by payment_id order by consumed_at) = 1
