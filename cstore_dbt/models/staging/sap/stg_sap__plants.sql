-- One row per store, from SAP plant master T001W.
with source as (
    select * from {{ source('sap', 't001w') }}
    where mandt = '{{ var("sap_client") }}'
)

select
    werks                as store_id,
    name1                as store_name,
    stras                as street_address,
    initcap(ort01)       as city,
    regio                as state_code,
    pstlz                as postal_code,
    land1                as country_code,
    vkorg                as sales_org_id
from source
