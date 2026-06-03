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

with requests as (
    select * from {{ ref('stg_payments__requests') }}
    {% if is_incremental() %}
    where requested_at > (select max(requested_at) - interval '{{ lookback_minutes }} minutes' from {{ this }})
    {% endif %}
),

rejections as (
    select * from {{ ref('stg_payments__rejections') }}
    {% if is_incremental() %}
    -- a rejection relevant to the look-back window has its request within it too
    where rejected_at > (select max(requested_at) - interval '{{ lookback_minutes }} minutes' from {{ this }})
    {% endif %}
),

-- Transform: attach the rejection (if any), derive status
resolved as (
    select
        r.payment_id,
        r.amount,
        r.requested_at,
        rej.rejected_at,
        case
            when rej.payment_id is not null then 'rejected'
            when {{ payments_now() }} >= r.requested_at + interval '{{ grace_minutes }} minutes' then 'accepted'
            else 'pending'
        end as status,
        {{ payments_now() }} as status_evaluated_at
    from requests r
    left join rejections rej using (payment_id)
)

select * from resolved
