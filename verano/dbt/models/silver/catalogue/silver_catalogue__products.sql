-- Product groups (styles) — the parent grain above variants.
with source as (
    select * from {{ source('bronze_catalogue', 'products') }}
)

select
    product_group_id,
    style_name,
    category_id,
    department,
    brand_line,
    pattern,
    fabric,
    price_band,
    base_price::double                   as base_price,
    season,
    description,
    ingested_at::timestamp               as ingested_at
from source
