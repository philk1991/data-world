-- Email engagement events, typed. Click rows carry encoded_customer_id — the same
-- deterministic identity signal exposed by email-sourced web sessions.
with source as (
    select * from {{ source('bronze_email', 'email_events') }}
)

select
    email_event_id,
    campaign_id,
    campaign_name,
    customer_id,
    event_type,
    event_at::timestamp                  as event_at,
    promoted_product_id,
    promoted_category,
    encoded_customer_id,
    ingested_at::timestamp               as ingested_at
from source
