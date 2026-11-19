-- Product dimension: one row per product, with category.
with materials as (
    select * from {{ ref('stg_sap__materials') }}
),

descriptions as (
    select * from {{ ref('stg_sap__material_descriptions') }}
),

categories as (
    select * from {{ ref('stg_sap__material_groups') }}
)

select
    materials.product_id,
    materials.product_number,
    descriptions.product_name,
    materials.category_id,
    categories.category_name,
    materials.category_id = 'FUEL01'          as is_fuel,
    materials.base_uom,
    materials.created_date,
    not materials.is_flagged_for_deletion     as is_active
from materials
left join descriptions
    on materials.product_id = descriptions.product_id
left join categories
    on materials.category_id = categories.category_id
