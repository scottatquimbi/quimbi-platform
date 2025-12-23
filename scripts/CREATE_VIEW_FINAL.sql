-- ============================================================================
-- Create Combined Sales View in Azure SQL
-- ============================================================================
-- VERIFIED: Product_Sales_Order.OrderID = SALES_DATA_ORDER.Id ✅
-- Run this in Azure Portal: SQL databases → Shopfiy → Query editor
-- Login: Quimby / +BZznTX7c
-- ============================================================================

CREATE OR ALTER VIEW vw_Combined_Sales AS
SELECT
    -- Order identifiers
    p.OrderID as order_id,
    p.OrderNumber as order_number,
    p.Customer_ID as customer_id,

    -- Time dimensions (from Product_Sales_Order)
    p.Date as order_date,
    p.CreatedAt as created_at,
    p.Year as year,
    p.Quarter as quarter,
    p.Month as month,
    p.MonthName as month_name,
    p.Week as week,
    p.Day as day,
    p.WeekDay as week_day,

    -- Product details (from Product_Sales_Order)
    p.Sku as sku,
    p.ProductId as product_id,
    p.Title as product_name,
    p.VariantTitle as variant_name,
    p.ProductType as product_type,
    p.Category as category,

    -- Sales metrics - line item level (from Product_Sales_Order)
    p.QTY as quantity,
    p.Sales as line_item_sales,
    p.TotalDiscount as line_item_discount,
    p.Refunds as line_item_refunds,
    p.Currency as currency,
    p.Source as sales_channel,

    -- Order-level enrichment (from SALES_DATA_ORDER)
    s.Latitude as latitude,
    s.Longitude as longitude,
    s.FulfillmentStatus as fulfillment_status,
    s.FinancialStatus as financial_status,
    s.TotalPrice as order_total,
    s.ItemQTY as order_total_items

FROM Product_Sales_Order p
LEFT JOIN SALES_DATA_ORDER s
    ON p.OrderID = s.Id;  -- Verified: IDs match ✅

GO

-- ============================================================================
-- Verify the view was created successfully
-- ============================================================================

PRINT 'View created successfully! Running verification tests...';
PRINT '';

-- Test 1: Row count
SELECT COUNT(*) as total_rows FROM vw_Combined_Sales;

-- Test 2: Sample data
SELECT TOP 5 * FROM vw_Combined_Sales ORDER BY order_date DESC;

-- Test 3: Match quality
SELECT
    COUNT(*) as total_rows,
    COUNT(latitude) as rows_with_location,
    COUNT(fulfillment_status) as rows_with_status,
    CAST(COUNT(latitude) * 100.0 / COUNT(*) AS DECIMAL(5,2)) as match_percentage
FROM vw_Combined_Sales;

-- Test 4: Date range
SELECT
    MIN(order_date) as earliest_order,
    MAX(order_date) as latest_order,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT product_id) as unique_products
FROM vw_Combined_Sales;

PRINT '';
PRINT '✅ View is ready to sync to Railway Postgres!';
PRINT '';
PRINT 'Next step: Run sync_combined_sales_simple.py';

GO
