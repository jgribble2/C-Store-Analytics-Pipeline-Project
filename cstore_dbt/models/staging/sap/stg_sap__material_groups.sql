-- One row per product category (SAP material group), English text only.
with source as (
    select * from {{ source('sap', 't023t') }}
    where mandt = '{{ var("sap_client") }}'
      and spras = 'E'
)

select
    matkl     as category_id,
    wgbez     as category_name
from source
