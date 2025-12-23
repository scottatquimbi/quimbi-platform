-- ============================================================================
-- Export Combined Sales Data from Azure SQL (Manual Method)
-- ============================================================================
-- If Python script doesn't work, run this query in VS Code and export results
-- ============================================================================

-- This query combines Product_Sales_Order and SALES_DATA_ORDER
-- Run this in VS Code Azure SQL connection, then export to CSV

SELECT
    -- Order identifiers
    p.OrderID as order_id,
    p.OrderNumber as order_number,
    p.Customer_ID as customer_id,

    -- Time dimensions
    p.Date as order_date,
    p.CreatedAt as created_at,
    p.Year as year,
    p.Quarter as quarter,
    p.Month as month,
    p.MonthName as month_name,
    p.Week as week,
    p.Day as day,
    p.WeekDay as week_day,

    -- Product details
    p.Sku as sku,
    p.ProductId as product_id,
    p.Title as product_name,
    p.VariantTitle as variant_name,
    p.ProductType as product_type,
    p.Category as category,

    -- Sales metrics
    p.QTY as quantity,
    p.Sales as line_item_sales,
    p.TotalDiscount as line_item_discount,
    p.Refunds as line_item_refunds,
    p.Currency as currency,
    p.Source as sales_channel,

    -- Order-level enrichment
    s.Latitude as latitude,
    s.Longitude as longitude,
    s.FulfillmentStatus as fulfillment_status,
    s.FinancialStatus as financial_status,
    s.TotalPrice as order_total,
    s.ItemQTY as order_total_items

FROM dbo.PRODUCT_SALES_ORDER p
LEFT JOIN dbo.SALES_DATA_ORDERS s ON p.OrderID = s.Id
ORDER BY p.Date;

-- ============================================================================
-- After running this query in VS Code:
-- ============================================================================
-- 1. Right-click on results pane
-- 2. Select "Save as CSV" or "Export to CSV"
-- 3. Save as: combined_sales_export.csv
-- 4. Then run: python scripts/upload_csv_to_railway.py combined_sales_export.csv
-- ============================================================================
