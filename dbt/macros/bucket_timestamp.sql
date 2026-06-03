{#
    Truncate a timestamp to the configured payments bucket size (in minutes).

    Controlled by the `payments_bucket_minutes` var (e.g. 1 or 5). Coarser buckets
    mean fewer rows in the serving table and faster dashboard queries — toggle it to
    match how granular the business actually needs the view to be.

    DuckDB uses time_bucket(); the Snowflake equivalent is
    time_slice(<column>, <n>, 'MINUTE').

    NOTE: changing the bucket size changes the model's grain — run the dependent
    model with --full-refresh after toggling so it is rebuilt at the new resolution.
#}
{% macro bucket_timestamp(column) %}
    time_bucket(interval '{{ var('payments_bucket_minutes', 1) }} minutes', {{ column }})
{% endmacro %}
