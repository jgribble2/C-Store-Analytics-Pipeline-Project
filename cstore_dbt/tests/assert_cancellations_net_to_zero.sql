-- A cancelled sale plus its S1 cancellation document should net to $0 in fct_sales.
-- Returns any original document whose cancellation does not fully reverse it.
with cancelled_activity as (
    select
        coalesce(headers.cancels_billing_doc_id, headers.billing_doc_id) as original_doc_id,
        sum(sales.net_sales) as net_sales
    from {{ ref('fct_sales') }} as sales
    inner join {{ ref('stg_sap__billing_headers') }} as headers
        on sales.billing_doc_id = headers.billing_doc_id
    where sales.is_cancelled_activity
    group by 1
)

select *
from cancelled_activity
where abs(net_sales) > 0.001
