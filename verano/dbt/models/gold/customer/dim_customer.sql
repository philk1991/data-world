-- dim_customer as a Type-2 slowly-changing dimension built from the version
-- history. valid_from = when the version became effective; valid_to = the next
-- version's effective_at (null for the current version). This is where the
-- consent/attribute change history becomes queryable "as at" any date.
with versions as (
    select * from {{ ref('silver_customers__versions') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'version_number']) }} as customer_sk,
    customer_id,
    version_number,
    change_reason,
    effective_at                                               as valid_from,
    lead(effective_at) over (
        partition by customer_id order by version_number
    )                                                          as valid_to,
    lead(effective_at) over (
        partition by customer_id order by version_number
    ) is null                                                  as is_current,
    first_name,
    last_name,
    email,
    brand_line_affinity,
    home_size,
    prefers_petite,
    region,
    postcode_area,
    signup_date,
    loyalty_member,
    loyalty_tier,
    email_consent,
    marketing_consent,
    data_processing_consent
from versions
