# Combined Sales Data Pipeline - Complete

**Status:** ✅ Successfully uploaded 1.2M rows to Railway Postgres

**Date Completed:** October 22, 2025

---

## Overview

Successfully loaded combined sales data from two CSV sources into Railway Postgres database.

## Data Sources

### 1. product_sales_order.csv
- **Size:** 275MB
- **Rows:** 1,221,736 line items
- **Columns:** Product details, line-item sales, order information
- **Coverage:** 2021-01-26 to 2025-10-22

### 2. sales_data_orders.csv
- **Size:** 20MB
- **Rows:** 202,079 orders
- **Columns:** Geographic data, fulfillment status, order-level metrics

## Data Integration

**Join Strategy:** LEFT JOIN
```sql
Product_Sales_Order LEFT JOIN SALES_DATA_ORDER
ON order_id = id
```

**Result:**
- **Total rows:** 1,221,736 (all line items preserved)
- **Rows with location data:** 1,044,911 (85.5%)
- **Rows with fulfillment status:** 1,217,695 (99.7%)

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS combined_sales (
    id BIGSERIAL PRIMARY KEY,
    sync_timestamp TIMESTAMP DEFAULT NOW(),

    -- Order info
    order_id BIGINT,
    order_number BIGINT,
    order_date TIMESTAMP,
    created_at TIMESTAMP,

    -- Customer
    customer_id BIGINT,  -- NULLABLE (some rows have NULL)

    -- Product
    sku VARCHAR(255),
    product_id BIGINT,
    product_name TEXT,
    variant_name TEXT,
    product_type VARCHAR(255),
    category VARCHAR(255),

    -- Line item metrics
    quantity INTEGER,
    line_item_sales NUMERIC(10, 2),
    line_item_discount NUMERIC(10, 2),
    line_item_refunds NUMERIC(10, 2),
    currency VARCHAR(10),
    sales_channel VARCHAR(100),

    -- Date dimensions
    year INTEGER,
    quarter INTEGER,
    month INTEGER,
    month_name VARCHAR(20),
    week INTEGER,
    day INTEGER,
    week_day VARCHAR(20),

    -- Geographic (from SALES_DATA_ORDER)
    city VARCHAR(255),
    state VARCHAR(255),
    country VARCHAR(255),
    zip VARCHAR(20),

    -- Fulfillment (from SALES_DATA_ORDER)
    fulfillment_status VARCHAR(50)
);

-- Performance indexes
CREATE INDEX idx_combined_sales_customer ON combined_sales(customer_id);
CREATE INDEX idx_combined_sales_order_date ON combined_sales(order_date);
CREATE INDEX idx_combined_sales_product ON combined_sales(product_id);
CREATE INDEX idx_combined_sales_category ON combined_sales(category);
CREATE INDEX idx_combined_sales_sku ON combined_sales(sku);
CREATE INDEX idx_combined_sales_order_id ON combined_sales(order_id);
```

## Data Quality

### Coverage Statistics
```
Total records: 1,221,736
Date range: 2021-01-26 to 2025-10-22 (4+ years)
Unique customers: 93,564
Unique products: 22,318
Unique orders: 200,729
Records with location: 1,044,911 (85.5%)
Records with fulfillment status: 1,217,695 (99.7%)
```

### Data Quality Issues Resolved

**Issue 1: NULL customer_id**
- **Problem:** Some rows had NULL customer_id
- **Root cause:** Order-level data doesn't always have customer linkage
- **Resolution:** Changed schema to allow NULL customer_id

**Issue 2: Extra columns in CSV**
- **Problem:** CSV had unmapped column "TotalDiscounts"
- **Resolution:** Added column filtering to only select mapped columns

## Upload Process

### Script: `scripts/combine_and_upload_csv.py`

**Process:**
1. Read both CSV files using pandas
2. Rename columns to match schema
3. LEFT JOIN on order_id = id
4. Filter to only mapped columns
5. Upload in chunks of 5,000 rows
6. Create performance indexes

**Upload Time:** ~5-7 minutes for 1.2M rows

**Command:**
```bash
export DATABASE_URL="postgresql://postgres:JSKjhRNwAbpJWgRysXyFKNUcopesLIfq@switchyard.proxy.rlwy.net:47164/railway"
python3 scripts/combine_and_upload_csv.py
```

## Future Data Sync Options

### Option 1: Re-run CSV Upload (Current)
**When:** As needed when CSVs are updated
```bash
python3 scripts/combine_and_upload_csv.py
```
- Drops and recreates table
- Uploads all data fresh
- Takes ~5-7 minutes

### Option 2: Azure SQL Direct Sync (Future)
**When:** Azure SQL firewall allows Railway IP (162.220.232.163)

**Setup:**
1. Whitelist Railway IP in Azure SQL firewall
2. Deploy `scripts/sync_combined_sales_simple.py` to Railway
3. Set up automated daily sync via admin API endpoints

**Commands:**
```bash
# Dry-run test
curl -X POST "https://your-app.railway.app/admin/sync-sales?mode=dry-run&limit=100&admin_key=<ADMIN_KEY>"

# Full sync
curl -X POST "https://your-app.railway.app/admin/sync-sales?mode=full&admin_key=<ADMIN_KEY>"

# Incremental (daily)
curl -X POST "https://your-app.railway.app/admin/sync-sales?mode=incremental&admin_key=<ADMIN_KEY>"
```

## Admin API Endpoints

### Check Sync Status
```bash
curl -X POST "https://your-app.railway.app/admin/sync-status?admin_key=<ADMIN_KEY>"
```

**Response:**
```json
{
  "sync_info": {
    "database_url": "postgresql://...",
    "table_exists": true,
    "table_name": "combined_sales"
  },
  "row_count": 1221736,
  "latest_record": {
    "order_date": "2025-10-22T00:00:00",
    "order_id": 5234567890
  },
  "date_range": {
    "earliest": "2021-01-26T00:00:00",
    "latest": "2025-10-22T00:00:00"
  }
}
```

### Trigger Manual Sync
```bash
curl -X POST "https://your-app.railway.app/admin/sync-sales?mode=dry-run&admin_key=<ADMIN_KEY>"
```

## Verification Queries

### Row Count
```sql
SELECT COUNT(*) FROM combined_sales;
-- Expected: 1,221,736
```

### Date Range
```sql
SELECT
    MIN(order_date) as earliest_date,
    MAX(order_date) as latest_date
FROM combined_sales;
-- Expected: 2021-01-26 to 2025-10-22
```

### Sample Data
```sql
SELECT * FROM combined_sales
ORDER BY order_date DESC
LIMIT 10;
```

### Coverage Stats
```sql
SELECT
    COUNT(*) as total_records,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT product_id) as unique_products,
    COUNT(DISTINCT order_id) as unique_orders,
    COUNT(city) as records_with_location,
    ROUND(100.0 * COUNT(city) / COUNT(*), 2) as location_coverage_pct
FROM combined_sales;
```

## Next Steps

1. ✅ **Data loaded** - 1.2M rows successfully uploaded
2. ✅ **Indexes created** - Performance optimized
3. ✅ **Verification complete** - Data quality confirmed
4. ⏳ **Azure SQL firewall** - Waiting for IP whitelist
5. ⏳ **Automated sync** - Will activate once firewall updated

## Files

- **Upload script:** `scripts/combine_and_upload_csv.py`
- **Source CSVs:**
  - `product_sales_order.csv` (275MB)
  - `sales_data_orders.csv` (20MB)
- **Sync script (future):** `scripts/sync_combined_sales_simple.py`
- **Admin endpoints:** `backend/main.py` lines 278-349

## Support

For questions or issues:
- Check Railway logs: `railway logs`
- Review this documentation
- Contact: scott@quimbi.ai

---

**Created:** October 22, 2025
**Last Updated:** October 22, 2025
**Status:** Production ready ✅
