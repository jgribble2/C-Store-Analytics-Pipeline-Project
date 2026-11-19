-- One row per product, English description only, from SAP MAKT.
with source as (
    select * from {{ source('sap', 'makt') }}
    where mandt = '{{ var("sap_client") }}'
      and spras = 'E'
)

select
    matnr             as product_id,
    initcap(maktx)    as product_name
from source
