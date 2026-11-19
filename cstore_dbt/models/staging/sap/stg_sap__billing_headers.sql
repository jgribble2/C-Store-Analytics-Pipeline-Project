-- One row per billing document (POS basket, return, or cancellation), from SAP VBRK.
-- SAP stores amounts as positive numbers; the billing type decides the sign.
with source as (
    select * from {{ source('sap', 'vbrk') }}
    where mandt = '{{ var("sap_client") }}'
)

select
    vbeln                                                 as billing_doc_id,
    fkart                                                 as billing_type,
    case fkart
        when 'ZPOS' then 'Sale'
        when 'ZRET' then 'Return'
        when 'S1'   then 'Cancellation'
    end                                                   as transaction_type,
    case when fkart in ('ZRET', 'S1') then -1 else 1 end  as amount_sign,
    vkorg                                                 as sales_org_id,
    try_to_date(nullif(fkdat, '00000000'), 'YYYYMMDD')    as billing_date,
    try_to_date(nullif(erdat, '00000000'), 'YYYYMMDD')    as created_date,
    try_to_time(erzet, 'HH24MISS')                        as created_time,
    kunag                                                 as customer_id,
    waerk                                                 as currency_code,
    try_to_number(netwr, 15, 2)                           as net_amount,
    try_to_number(mwsbk, 15, 2)                           as tax_amount,
    coalesce(fksto = 'X', false)                          as is_cancelled,
    sfakn                                                 as cancels_billing_doc_id
from source
