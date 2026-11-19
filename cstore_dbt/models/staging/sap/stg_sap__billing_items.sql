-- One row per billing document line, from SAP VBRP. Amounts are unsigned, as in SAP.
with source as (
    select * from {{ source('sap', 'vbrp') }}
    where mandt = '{{ var("sap_client") }}'
)

select
    vbeln || '-' || posnr             as billing_line_id,
    vbeln                             as billing_doc_id,
    try_to_number(posnr)              as line_number,
    matnr                             as product_id,
    matkl                             as category_id,
    werks                             as store_id,
    try_to_number(fkimg, 13, 3)       as quantity,
    vrkme                             as sales_uom,
    try_to_number(netwr, 15, 2)       as net_amount,
    try_to_number(wavwr, 15, 2)       as cost_amount,
    try_to_number(mwsbp, 15, 2)       as tax_amount
from source
