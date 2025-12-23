-- ============================================================================
-- Export INCREMENTAL Combined Sales Data from Azure SQL
-- ============================================================================
-- Run this in VS Code Azure SQL connection to export only NEW data
-- ============================================================================
-- This query gets orders AFTER October 22, 2025 (the last sync date)
-- ============================================================================

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
WHERE p.Date > '2025-10-22'  -- ⬅️ ONLY NEW ORDERS AFTER LAST SYNC
ORDER BY p.Date;

-- ============================================================================
-- INSTRUCTIONS:
-- ============================================================================
-- 1. Open this file in VS Code
-- 2. Make sure you're connected to: linda.database.windows.net/Shopfiy
-- 3. Run the query (Cmd+Shift+E or right-click → Execute Query)
-- 4. Wait for results to load (may take 30-60 seconds)
-- 5. Right-click on results pane → "Save as CSV"
-- 6. Save as: combined_sales_incremental.csv
-- 7. Then run: python3 scripts/upload_incremental_to_railway.py
-- ============================================================================

-- Expected: Should return ~10,000-20,000 rows (12 days of new orders)
-- If it returns 0 rows: Data is already up to date!
-- ============================================================================
