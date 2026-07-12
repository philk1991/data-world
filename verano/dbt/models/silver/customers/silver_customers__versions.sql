-- Customer version history (SCD source). One row per (customer, version); gold
-- turns this into a Type-2 dimension with valid_from/valid_to.
with source as (
    select * from {{ source('bronze_customers', 'customer_versions') }}
)

select
    customer_id,
    version_number::int                  as version_number,
    effective_at::timestamp              as effective_at,
    change_reason,
    first_name,
    last_name,
    email,
    brand_line_affinity,
    home_size,
    prefers_petite::boolean              as prefers_petite,
    region,
    postcode_area,
    signup_date::date                    as signup_date,
    loyalty_member::boolean              as loyalty_member,
    loyalty_tier,
    email_consent::boolean               as email_consent,
    marketing_consent::boolean           as marketing_consent,
    data_processing_consent::boolean     as data_processing_consent,
    ingested_at::timestamp               as ingested_at
from source
