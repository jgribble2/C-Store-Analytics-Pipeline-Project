{#
    Use the custom schema name as-is (STAGING, INTERMEDIATE, MARTS) instead of
    dbt's default of prefixing it with the target schema (DBT_DEV_STAGING).
    Models without a custom schema fall back to the target schema.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim | upper }}
    {%- endif -%}
{%- endmacro %}
