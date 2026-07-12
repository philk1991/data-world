-- Category dimension with the parent (department) name flattened on.
with categories as (
    select * from {{ ref('silver_catalogue__categories') }}
)

select
    c.category_id,
    c.category_name,
    c.category_level,
    c.department,
    c.parent_category_id,
    p.category_name                      as parent_category_name
from categories c
left join categories p on c.parent_category_id = p.category_id
