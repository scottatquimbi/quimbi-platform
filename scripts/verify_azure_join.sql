-- ============================================================================
-- Verify Join Keys Between Product_Sales_Order and SALES_DATA_ORDER
-- ============================================================================
-- Run this in Azure SQL Portal to verify the correct join relationship
-- ============================================================================

-- Test 1: Check if OrderID = Id (RECOMMENDED JOIN)
-- ============================================================================
PRINT 'TEST 1: Checking if Product_Sales_Order.OrderID = SALES_DATA_ORDER.Id';
PRINT '======================================================================';

SELECT TOP 20
    p.OrderID as Product_OrderID,
    p.OrderNumber as Product_OrderNumber,
    p.Customer_ID as Product_CustomerID,
    p.Date as Product_Date,
    s.Id as Sales_Id,
    s.Customer_ID as Sales_CustomerID,
    s.date as Sales_Date,
    CASE
        WHEN s.Id IS NULL THEN '❌ NO MATCH'
        WHEN p.OrderID = s.Id THEN '✅ PERFECT MATCH'
        ELSE '⚠️  FOUND BUT DIFFERENT'
    END as Match_Status,
    CASE
        WHEN s.date IS NOT NULL THEN DATEDIFF(day, s.date, p.Date)
        ELSE NULL
    END as Date_Difference_Days
FROM Product_Sales_Order p
LEFT JOIN SALES_DATA_ORDER s ON p.OrderID = s.Id
ORDER BY p.Date DESC;

-- Summary statistics
SELECT
    COUNT(*) as Total_Product_Orders,
    COUNT(s.Id) as Matched_Sales_Orders,
    COUNT(*) - COUNT(s.Id) as Unmatched,
    CAST(COUNT(s.Id) * 100.0 / COUNT(*) AS DECIMAL(5,2)) as Match_Percentage
FROM Product_Sales_Order p
LEFT JOIN SALES_DATA_ORDER s ON p.OrderID = s.Id;

PRINT '';
PRINT 'If Match_Percentage > 90%, JOIN ON p.OrderID = s.Id is CORRECT ✅';
PRINT 'If Match_Percentage < 50%, try alternative joins below ⚠️';
PRINT '';

-- ============================================================================
-- Test 2: Check ID ranges (do they overlap?)
-- ============================================================================
PRINT 'TEST 2: Checking ID ranges for overlap';
PRINT '======================================================================';

SELECT
    'Product_Sales_Order.OrderID' as Source,
    MIN(OrderID) as Min_ID,
    MAX(OrderID) as Max_ID,
    COUNT(DISTINCT OrderID) as Unique_IDs
FROM Product_Sales_Order

UNION ALL

SELECT
    'SALES_DATA_ORDER.Id' as Source,
    MIN(Id) as Min_ID,
    MAX(Id) as Max_ID,
    COUNT(DISTINCT Id) as Unique_IDs
FROM SALES_DATA_ORDER;

PRINT '';
PRINT 'If ID ranges overlap significantly, OrderID = Id is likely correct ✅';
PRINT '';

-- ============================================================================
-- Test 3: Sample matched records (detailed inspection)
-- ============================================================================
PRINT 'TEST 3: Sample of matched records (detailed view)';
PRINT '======================================================================';

SELECT TOP 10
    '=== Product Sales Order ===' as Section,
    p.OrderID,
    p.OrderNumber,
    p.Customer_ID,
    p.Date as order_date,
    p.Sku,
    p.Title as product_name,
    p.QTY,
    p.Sales,
    '=== Sales Data Order ===' as Section2,
    s.Id,
    s.Customer_ID as sales_customer_id,
    s.date as sales_date,
    s.TotalPrice,
    s.ItemQTY,
    s.FulfillmentStatus,
    s.FinancialStatus,
    '=== Match Info ===' as Section3,
    CASE WHEN p.OrderID = s.Id THEN '✅ IDs MATCH' ELSE '❌ IDs DIFFER' END as ID_Match,
    CASE WHEN p.Customer_ID = s.Customer_ID THEN '✅ SAME CUSTOMER' ELSE '❌ DIFF CUSTOMER' END as Customer_Match,
    DATEDIFF(hour, s.date, p.Date) as Hours_Difference
FROM Product_Sales_Order p
INNER JOIN SALES_DATA_ORDER s ON p.OrderID = s.Id
WHERE p.Date >= DATEADD(day, -30, GETDATE())  -- Last 30 days
ORDER BY p.Date DESC;

-- ============================================================================
-- Test 4: Check for date mismatches (your concern about dates)
-- ============================================================================
PRINT 'TEST 4: Date mismatch analysis (product date vs sales date)';
PRINT '======================================================================';

SELECT
    DATEDIFF(day, s.date, p.Date) as Days_Difference,
    COUNT(*) as Occurrences,
    CAST(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() AS DECIMAL(5,2)) as Percentage
FROM Product_Sales_Order p
INNER JOIN SALES_DATA_ORDER s ON p.OrderID = s.Id
GROUP BY DATEDIFF(day, s.date, p.Date)
ORDER BY Occurrences DESC;

PRINT '';
PRINT 'Expected: Most records have 0-1 day difference (same day or next day) ✅';
PRINT 'If you see large differences (>2 days), investigate further ⚠️';
PRINT '';

-- ============================================================================
-- Test 5: Alternative join methods (if OrderID doesn't work)
-- ============================================================================
PRINT 'TEST 5: Alternative join methods (backup options)';
PRINT '======================================================================';

-- Option A: Customer + Date (same day)
PRINT 'Option A: Join on Customer_ID + Date (exact match)';
SELECT
    COUNT(*) as Matched_Records,
    COUNT(DISTINCT p.OrderID) as Unique_Orders
FROM Product_Sales_Order p
INNER JOIN SALES_DATA_ORDER s
    ON p.Customer_ID = s.Customer_ID
    AND CAST(p.Date AS DATE) = s.date;

-- Option B: Customer + Date (within 1 day)
PRINT 'Option B: Join on Customer_ID + Date (within 1 day)';
SELECT
    COUNT(*) as Matched_Records,
    COUNT(DISTINCT p.OrderID) as Unique_Orders
FROM Product_Sales_Order p
INNER JOIN SALES_DATA_ORDER s
    ON p.Customer_ID = s.Customer_ID
    AND ABS(DATEDIFF(day, s.date, p.Date)) <= 1;

-- ============================================================================
-- Test 6: Data quality checks
-- ============================================================================
PRINT 'TEST 6: Data quality checks';
PRINT '======================================================================';

-- Check for NULL IDs
SELECT
    'Product_Sales_Order' as Table_Name,
    COUNT(*) as Total_Rows,
    COUNT(OrderID) as Non_Null_OrderID,
    COUNT(*) - COUNT(OrderID) as Null_OrderID
FROM Product_Sales_Order

UNION ALL

SELECT
    'SALES_DATA_ORDER' as Table_Name,
    COUNT(*) as Total_Rows,
    COUNT(Id) as Non_Null_Id,
    COUNT(*) - COUNT(Id) as Null_Id
FROM SALES_DATA_ORDER;

-- Check for duplicate IDs
SELECT
    'Product_Sales_Order duplicates' as Check_Type,
    COUNT(*) as Duplicate_OrderIDs
FROM (
    SELECT OrderID, COUNT(*) as cnt
    FROM Product_Sales_Order
    GROUP BY OrderID
    HAVING COUNT(*) > 1
) dup;

-- ============================================================================
-- RECOMMENDED JOIN QUERY (based on results)
-- ============================================================================
PRINT '';
PRINT '======================================================================';
PRINT 'RECOMMENDED: If Test 1 shows >90% match, use this view:';
PRINT '======================================================================';
PRINT '';
PRINT 'CREATE OR ALTER VIEW vw_Combined_Sales AS';
PRINT 'SELECT';
PRINT '    p.OrderID, p.OrderNumber, p.Customer_ID,';
PRINT '    p.Date, p.Sku, p.ProductId, p.Title, ...';
PRINT '    s.Latitude, s.Longitude, s.FulfillmentStatus, ...';
PRINT 'FROM Product_Sales_Order p';
PRINT 'LEFT JOIN SALES_DATA_ORDER s ON p.OrderID = s.Id;';
PRINT '';
PRINT '======================================================================';
PRINT 'ALTERNATIVE: If Test 1 shows <50% match, use this view:';
PRINT '======================================================================';
PRINT '';
PRINT 'CREATE OR ALTER VIEW vw_Combined_Sales AS';
PRINT 'SELECT';
PRINT '    p.OrderID, p.OrderNumber, p.Customer_ID,';
PRINT '    p.Date, p.Sku, p.ProductId, p.Title, ...';
PRINT '    s.Latitude, s.Longitude, s.FulfillmentStatus, ...';
PRINT 'FROM Product_Sales_Order p';
PRINT 'LEFT JOIN SALES_DATA_ORDER s';
PRINT '    ON p.Customer_ID = s.Customer_ID';
PRINT '    AND ABS(DATEDIFF(day, s.date, p.Date)) <= 1;';
PRINT '';
PRINT '======================================================================';
PRINT 'END OF VERIFICATION TESTS';
PRINT '======================================================================';
