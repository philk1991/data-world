-- Search logs, typed. converted / clicked_position describe search effectiveness.
-- _true_customer_id is evaluation-only.
with source as (
    select * from {{ source('bronze_search', 'search_logs') }}
)

select
    search_id,
    event_at::timestamp                  as event_at,
    anonymous_id,
    customer_id,
    query_text,
    category_id,
    results_count::int                   as results_count,
    clicked_position::int                as clicked_position,
    clicked_product_id,
    converted::boolean                   as converted,
    _true_customer_id,
    ingested_at::timestamp               as ingested_at
from source
