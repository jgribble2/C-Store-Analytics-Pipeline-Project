-- One row per product, from SAP material master MARA.
with source as (
    select * from {{ source('sap', 'mara') }}
    where mandt = '{{ var("sap_client") }}'
)

select
    matnr                                                 as product_id,      -- keep leading zeros for joins
    ltrim(matnr, '0')                                     as product_number,  -- display version
    try_to_date(nullif(ersda, '00000000'), 'YYYYMMDD')    as created_date,
    coalesce(lvorm = 'X', false)                          as is_flagged_for_deletion,
    mtart                                                 as material_type,
    matkl                                                 as category_id,
    meins                                                 as base_uom,
    try_to_number(brgew, 13, 3)                           as gross_weight,
    gewei                                                 as weight_uom
from source
