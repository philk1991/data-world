{#
    The "current time" used to resolve payment status (the grace-window comparison
    and status_evaluated_at). Wrapping now() in a macro gives unit tests an
    injectable seam: override `payments_now` to a fixed timestamp so the
    accepted/rejected/pending logic can be asserted deterministically.
#}
{% macro payments_now() %}
    now()
{% endmacro %}
