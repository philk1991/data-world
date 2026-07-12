-- Product dimension at VARIANT (SKU) grain, with the product_group_id parent and
-- the group description carried through (used for embeddings in Layer 5).
with variants as (
    select * from {{ ref('silver_catalogue__variants') }}
),

products as (
    select * from {{ ref('silver_catalogue__products') }}
)

select
    v.variant_id,
    v.product_group_id,
    v.style_name,
    p.description,
    v.category_id,
    v.department,
    v.brand_line,
    v.colour,
    v.size,
    v.size_range,
    v.pattern,
    v.fabric,
    v.price_band,
    v.price,
    v.season,
    v.stock_level,
    v.is_in_stock,
    v.is_active
from variants v
left join products p using (product_group_id)
