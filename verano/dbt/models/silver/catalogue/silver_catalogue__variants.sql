-- Sellable SKU grain. Adds a derived is_in_stock flag from the stock level.
with source as (
    select * from {{ source('bronze_catalogue', 'product_variants') }}
)

select
    variant_id,
    product_group_id,
    style_name,
    category_id,
    department,
    brand_line,
    colour,
    size,
    size_range,
    pattern,
    fabric,
    price_band,
    price::double                        as price,
    season,
    stock_level::int                     as stock_level,
    stock_level > 0                      as is_in_stock,
    is_active::boolean                   as is_active,
    ingested_at::timestamp               as ingested_at
from source
