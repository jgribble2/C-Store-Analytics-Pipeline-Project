-- One row per store, from the custom Z-table of store attributes.
with source as (
    select * from {{ source('sap', 'zstore_attr') }}
    where mandt = '{{ var("sap_client") }}'
)

select
    werks                                                     as store_id,
    store_format,
    coalesce(fuel_flag = 'X', false)                          as has_fuel,
    try_to_number(sq_ft)                                      as square_feet,
    try_to_number(fuel_positions)                             as fuel_positions,
    district                                                  as district_id,
    try_to_date(nullif(open_date, '00000000'), 'YYYYMMDD')    as opened_date,
    try_to_date(nullif(close_date, '00000000'), 'YYYYMMDD')   as closed_date
from source
