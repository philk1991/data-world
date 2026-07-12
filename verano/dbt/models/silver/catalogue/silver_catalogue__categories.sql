-- Category hierarchy nodes, lightly typed. One row per category (department or leaf).
with source as (
    select * from {{ source('bronze_catalogue', 'categories') }}
)

select
    category_id,
    category_name,
    parent_category_id,
    category_level::int                  as category_level,
    department,
    ingested_at::timestamp               as ingested_at
from source
