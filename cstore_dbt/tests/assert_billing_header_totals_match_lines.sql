-- Each billing header's NETWR should equal the sum of its line items (within a cent).
-- Returns any document where they disagree; the test passes when no rows come back.
with line_totals as (
    select
        billing_doc_id,
        sum(net_amount) as line_total
    from {{ ref('stg_sap__billing_items') }}
    group by billing_doc_id
)

select
    headers.billing_doc_id,
    headers.net_amount as header_total,
    line_totals.line_total
from {{ ref('stg_sap__billing_headers') }} as headers
inner join line_totals
    on headers.billing_doc_id = line_totals.billing_doc_id
where abs(headers.net_amount - line_totals.line_total) > 0.01
