-- Sales fact: one row per billing document line (signed).
-- Sales are positive; returns and cancellations are negative.
with lines as (
    select * from {{ ref('int_sales_lines__signed') }}
)

select
    billing_line_id                                           as sales_line_id,
    billing_doc_id,
    line_number,
    billing_type,
    transaction_type,
    sale_date,
    sale_time,
    sale_hour,
    store_id,
    product_id,
    category_id,

    -- A cancelled sale and its S1 reversal net to zero. Reports can keep both
    -- (totals are already correct) or filter both out with this flag.
    (is_cancelled or billing_type = 'S1')                     as is_cancelled_activity,

    quantity,
    iff(sales_uom = 'GAL', quantity, 0)                       as fuel_gallons,
    iff(sales_uom = 'EA', quantity, 0)                        as merchandise_units,
    net_sales,
    cost_amount,
    net_sales - cost_amount                                   as gross_margin,
    tax_amount
from lines
