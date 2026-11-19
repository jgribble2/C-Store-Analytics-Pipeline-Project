-- Reconcile MicroStrategy (Strategy Mosaic) totals against the dbt marts in Snowflake.
-- Compare the output with the "Annual Summary" grid in the C-Store Sales Dashboard.
-- Expected (seed 42): 2024 = $1,996,531.03 / 158,045 baskets; 2025 = $2,451,888.37 / 183,486 baskets.

WITH yearly AS (
    SELECT
        YEAR(sale_date)                                    AS sale_year,
        SUM(net_sales)                                     AS net_sales,
        SUM(gross_margin)                                  AS gross_margin,
        COUNT(DISTINCT IFF(transaction_type = 'Sale' AND NOT is_cancelled_activity,
                           billing_doc_id, NULL))          AS basket_count
    FROM CSTORE.MARTS.FCT_SALES
    GROUP BY 1
)

SELECT
    sale_year,
    net_sales,
    ROUND(gross_margin / net_sales * 100, 1)               AS gross_margin_pct,
    basket_count,
    ROUND(net_sales / basket_count, 2)                     AS avg_basket_size,
    LAG(net_sales) OVER (ORDER BY sale_year)               AS net_sales_ly,
    ROUND((net_sales / LAG(net_sales) OVER (ORDER BY sale_year) - 1) * 100, 1)
                                                           AS net_sales_yoy_pct
FROM yearly
ORDER BY sale_year;
