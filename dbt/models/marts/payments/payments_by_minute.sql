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

with status as (
    select * from {{ ref('payment_status') }}
    {% if is_incremental() %}
    where requested_at > (select max(request_bucket) - interval '{{ lookback_minutes }} minutes' from {{ this }})
    {% endif %}
),

by_bucket as (
    select
        {{ bucket_timestamp('requested_at') }}              as request_bucket,
        count(*)                                            as payments_total,
        count(*) filter (where status = 'accepted')         as payments_accepted,
        count(*) filter (where status = 'rejected')         as payments_rejected,
        count(*) filter (where status = 'pending')          as payments_pending,
        sum(amount)                                         as amount_total,
        sum(amount) filter (where status = 'accepted')      as amount_accepted,
        sum(amount) filter (where status = 'rejected')      as amount_rejected,
        sum(amount) filter (where status = 'pending')       as amount_pending,
        now()                                               as refreshed_at
    from status
    group by 1
)

select * from by_bucket
order by request_bucket
