-- ============================================================================
-- Create Combined Sales View/Table in Azure SQL
-- ============================================================================
-- This combines Product_Sales_Order and SALES_DATA_ORDER into a single table
-- for easier syncing to Railway Postgres.
--
-- Run this in Azure SQL Server (linda.database.windows.net/Shopfiy)
-- ============================================================================

-- Option 1: Create as VIEW (recommended - always up to date)
-- ============================================================================
CREATE OR ALTER VIEW vw_Combined_Sales AS
SELECT
    -- Primary Keys
    p.OrderID as order_id,
    p.OrderNumber as order_number,
    p.Customer_ID as customer_id,

    -- Time Dimensions
    p.Date as order_date,
    p.CreatedAt as created_at,
    p.Year as year,
    p.Quarter as quarter,
    p.Month as month,
    p.MonthName as month_name,
    p.Week as week,
    p.Day as day,
    p.WeekDay as week_day,

    -- Product Details (from Product_Sales_Order)
    p.Sku as sku,
    p.ProductId as product_id,
    p.Title as product_name,
    p.VariantTitle as variant_name,
    p.ProductType as product_type,
    p.Category as category,

    -- Sales Metrics (line-item level from Product_Sales_Order)
    p.QTY as quantity,
    p.Sales as line_item_sales,
    p.TotalDiscount as line_item_discount,
    p.Refunds as line_item_refunds,
    p.Currency as currency,
    p.Source as sales_channel,

    -- Order-Level Enrichment (from SALES_DATA_ORDER)
    s.Latitude as latitude,
    s.Longitude as longitude,
    s.FulfillmentStatus as fulfillment_status,
    s.FinancialStatus as financial_status,
    s.TotalPrice as order_total,
    s.ItemQTY as order_total_items

FROM Product_Sales_Order p
LEFT JOIN SALES_DATA_ORDER s
    ON p.OrderID = s.Id  -- Primary join on OrderID = Id
    -- Note: Dates may differ by 1 day (order time vs close of business)
    -- This is expected and OK - we're joining on IDs, not dates

-- ALTERNATIVE JOIN (use if OrderID match is poor):
-- LEFT JOIN SALES_DATA_ORDER s
--     ON p.Customer_ID = s.Customer_ID
--     AND ABS(DATEDIFF(day, s.date, p.Date)) <= 1  -- Allow 1 day difference
;

GO

-- ============================================================================
-- Option 2: Create as MATERIALIZED TABLE (faster queries, needs refresh)
-- ============================================================================
-- Uncomment if you prefer a physical table over a view

/*
-- Drop existing table if it exists
IF OBJECT_ID('Combined_Sales', 'U') IS NOT NULL
    DROP TABLE Combined_Sales;
GO

-- Create physical table
SELECT
    -- Primary Keys
    p.OrderID as order_id,
    p.OrderNumber as order_number,
    p.Customer_ID as customer_id,

    -- Time Dimensions
    p.Date as order_date,
    p.CreatedAt as created_at,
    p.Year as year,
    p.Quarter as quarter,
    p.Month as month,
    p.MonthName as month_name,
    p.Week as week,
    p.Day as day,
    p.WeekDay as week_day,

    -- Product Details
    p.Sku as sku,
    p.ProductId as product_id,
    p.Title as product_name,
    p.VariantTitle as variant_name,
    p.ProductType as product_type,
    p.Category as category,

    -- Sales Metrics
    p.QTY as quantity,
    p.Sales as line_item_sales,
    p.TotalDiscount as line_item_discount,
    p.Refunds as line_item_refunds,
    p.Currency as currency,
    p.Source as sales_channel,

    -- Order-Level Enrichment
    s.Latitude as latitude,
    s.Longitude as longitude,
    s.FulfillmentStatus as fulfillment_status,
    s.FinancialStatus as financial_status,
    s.TotalPrice as order_total,
    s.ItemQTY as order_total_items

INTO Combined_Sales
FROM Product_Sales_Order p
LEFT JOIN SALES_DATA_ORDER s
    ON p.OrderID = s.Id;
GO

-- Create indexes for performance
CREATE INDEX idx_combined_customer ON Combined_Sales(customer_id);
CREATE INDEX idx_combined_order_date ON Combined_Sales(order_date);
CREATE INDEX idx_combined_product ON Combined_Sales(product_id);
CREATE INDEX idx_combined_order_id ON Combined_Sales(order_id);
GO

-- To refresh the table later (add new records):
-- DELETE FROM Combined_Sales WHERE order_date < DATEADD(day, -1, GETDATE()); -- Keep last day
-- INSERT INTO Combined_Sales
-- SELECT ... (same query as above) WHERE p.Date >= DATEADD(day, -1, GETDATE());
*/

-- ============================================================================
-- Test Queries
-- ============================================================================

-- Check if view was created successfully
SELECT COUNT(*) as total_rows FROM vw_Combined_Sales;

-- See sample data
SELECT TOP 10 * FROM vw_Combined_Sales ORDER BY order_date DESC;

-- Verify join quality (how many rows have order-level data?)
SELECT
    COUNT(*) as total_rows,
    COUNT(latitude) as rows_with_location,
    COUNT(fulfillment_status) as rows_with_fulfillment,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT order_id) as unique_orders
FROM vw_Combined_Sales;

-- Check date range
SELECT
    MIN(order_date) as earliest_order,
    MAX(order_date) as latest_order,
    DATEDIFF(day, MIN(order_date), MAX(order_date)) as days_span
FROM vw_Combined_Sales;

-- ============================================================================
-- IMPORTANT: Verify Join Relationship
-- ============================================================================
-- We need to confirm if Product_Sales_Order.OrderID = SALES_DATA_ORDER.Id
-- Run this query to check:

SELECT
    'Product_Sales_Order.OrderID' as source,
    MIN(OrderID) as min_value,
    MAX(OrderID) as max_value,
    COUNT(DISTINCT OrderID) as unique_values
FROM Product_Sales_Order

UNION ALL

SELECT
    'SALES_DATA_ORDER.Id' as source,
    MIN(Id) as min_value,
    MAX(Id) as max_value,
    COUNT(DISTINCT Id) as unique_values
FROM SALES_DATA_ORDER;

-- Test if IDs overlap
SELECT TOP 5
    p.OrderID as product_order_id,
    s.Id as sales_data_id,
    p.OrderNumber,
    p.Customer_ID,
    p.Date,
    s.date,
    CASE WHEN s.Id IS NOT NULL THEN 'MATCHED' ELSE 'NO MATCH' END as join_status
FROM Product_Sales_Order p
LEFT JOIN SALES_DATA_ORDER s ON p.OrderID = s.Id
ORDER BY p.Date DESC;

-- ============================================================================
-- Notes:
-- ============================================================================
-- 1. VIEW (Option 1) - Always reflects current data, no maintenance needed
-- 2. TABLE (Option 2) - Faster queries, but needs periodic refresh
-- 3. Join is on OrderID = Id (VERIFY THIS IS CORRECT!)
-- 4. If OrderID != Id, use: customer_id + date join instead
-- ============================================================================
