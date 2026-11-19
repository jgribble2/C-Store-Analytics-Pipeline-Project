-- Store dimension: one row per store.
with plants as (
    select * from {{ ref('stg_sap__plants') }}
),

attributes as (
    select * from {{ ref('stg_sap__store_attributes') }}
)

select
    plants.store_id,
    plants.store_name,
    plants.street_address,
    plants.city,
    plants.state_code,
    plants.postal_code,
    plants.country_code,
    attributes.district_id,
    attributes.store_format,
    attributes.has_fuel,
    attributes.square_feet,
    attributes.fuel_positions,
    attributes.opened_date,
    attributes.closed_date,
    coalesce(attributes.opened_date <= '{{ var("comp_store_cutoff") }}'::date, false)
                                              as is_comparable_store
from plants
left join attributes
    on plants.store_id = attributes.store_id
