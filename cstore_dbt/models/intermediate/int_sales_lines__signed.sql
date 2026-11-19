-- Joins billing lines to their headers and applies the document-type sign,
-- so returns and cancellations subtract from sales instead of adding to them.
with items as (
    select * from {{ ref('stg_sap__billing_items') }}
),

headers as (
    select * from {{ ref('stg_sap__billing_headers') }}
)

select
    items.billing_line_id,
    items.billing_doc_id,
    items.line_number,
    headers.billing_type,
    headers.transaction_type,
    headers.billing_date                       as sale_date,
    headers.created_time                       as sale_time,
    hour(headers.created_time)                 as sale_hour,
    items.store_id,
    items.product_id,
    items.category_id,
    items.sales_uom,
    headers.is_cancelled,
    headers.cancels_billing_doc_id,
    items.quantity     * headers.amount_sign   as quantity,
    items.net_amount   * headers.amount_sign   as net_sales,
    items.cost_amount  * headers.amount_sign   as cost_amount,
    items.tax_amount   * headers.amount_sign   as tax_amount
from items
inner join headers
    on items.billing_doc_id = headers.billing_doc_id
