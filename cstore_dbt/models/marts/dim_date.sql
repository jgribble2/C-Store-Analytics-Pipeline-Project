-- Date dimension: one row per calendar day between the calendar_start_date and
-- calendar_end_date vars. Starts a year before the sales data so YoY comparisons work.
with days as (
    select
        dateadd(
            day,
            row_number() over (order by seq4()) - 1,
            '{{ var("calendar_start_date") }}'::date
        ) as date_day
    from table(generator(rowcount => 5000))
)

select
    date_day,
    year(date_day)                                     as year_number,
    quarter(date_day)                                  as quarter_number,
    'Q' || quarter(date_day) || ' ' || year(date_day)  as quarter_label,
    month(date_day)                                    as month_number,
    monthname(date_day)                                as month_short_name,
    to_char(date_day, 'YYYY-MM')                       as year_month,
    date_trunc('month', date_day)                      as month_start_date,
    date_trunc('week', date_day)                       as week_start_date,
    weekiso(date_day)                                  as iso_week_number,
    dayofweekiso(date_day)                             as day_of_week_number,  -- 1 = Monday
    dayname(date_day)                                  as day_short_name,
    dayofweekiso(date_day) in (6, 7)                   as is_weekend,
    dateadd(year, -1, date_day)                        as same_day_last_year
from days
where date_day <= '{{ var("calendar_end_date") }}'::date
