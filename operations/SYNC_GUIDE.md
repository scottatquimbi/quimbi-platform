# Quick Sync Guide - CSV Method (Works Now!)

**Status:** ✅ This method works TODAY without waiting for automated sync
**Time:** ~5-10 minutes
**Requirements:** VS Code with Azure SQL connection OR Python with pymssql

---

## Method 1: Python Script (Recommended)

### Step 1: Export Missing Data from Azure SQL

```bash
cd /Users/scottallen/unified-segmentation-ecommerce

# Export orders after October 22, 2025
python3 scripts/export_incremental_azure_to_csv.py

# Output: combined_sales_incremental.csv
```

**Expected output:**
```
🔄 Exporting INCREMENTAL Combined Sales Data from Azure SQL
📅 Fetching orders AFTER: 2025-10-22

Connecting to linda.database.windows.net/Shopfiy...
✅ Connected to Azure SQL

Fetching orders with Date > '2025-10-22'...
✅ Fetched 15,432 NEW rows

📅 Date range in export:
   From: 2025-10-23
   To:   2025-11-03

✅ Exported 15,432 rows to combined_sales_incremental.csv
📊 File size: 2.5 MB

✅ Export Complete!
```

### Step 2: Upload to Railway Postgres

```bash
# Set DATABASE_URL
export DATABASE_URL="postgresql://postgres:JSKjhRNwAbpJWgRysXyFKNUcopesLIfq@switchyard.proxy.rlwy.net:47164/railway"

# Upload the CSV
python3 scripts/upload_incremental_to_railway.py

# Or specify custom file:
# python3 scripts/upload_incremental_to_railway.py combined_sales_incremental.csv
```

**Expected output:**
```
📤 Uploading Incremental Sales Data to Railway Postgres

Reading combined_sales_incremental.csv...
✅ Loaded 15,432 rows

📅 Date range in CSV:
   From: 2025-10-23
   To:   2025-11-03

Connecting to Railway Postgres...
📊 Current database state:
   Rows: 1,221,736
   Latest order date: 2025-10-22

📤 Uploading 15,432 new rows...
   Mode: APPEND (existing data preserved)

✅ Successfully uploaded 15,432 rows

📊 After upload:
   Total rows: 1,237,168 (+15,432)
   Latest order date: 2025-11-03

✅ Row count verified!

🎉 Upload Complete!
Data is now up to date!
```

### Step 3: Verify Data is Fresh

```bash
export DATABASE_URL="postgresql://postgres:JSKjhRNwAbpJWgRysXyFKNUcopesLIfq@switchyard.proxy.rlwy.net:47164/railway"

psql $DATABASE_URL -c "SELECT MAX(order_date) as latest_order, COUNT(*) as total_rows, NOW() - MAX(order_date) as data_age FROM combined_sales;"
```

**Should show:**
```
   latest_order    | total_rows | data_age
-------------------+------------+----------
 2025-11-03        | 1,237,168  | 0 days
```

---

## Method 2: Manual SQL in VS Code (If Python Fails)

### Step 1: Export in VS Code

1. Open VS Code
2. Connect to Azure SQL: `linda.database.windows.net/Shopfiy`
3. Run this query:

```sql
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

FROM Product_Sales_Order p
LEFT JOIN SALES_DATA_ORDER s ON p.OrderID = s.Id
WHERE p.Date > '2025-10-22'  -- Only new orders!
ORDER BY p.Date;
```

4. Right-click results → "Save as CSV"
5. Save as: `combined_sales_incremental.csv`

### Step 2: Upload CSV

```bash
export DATABASE_URL="postgresql://postgres:JSKjhRNwAbpJWgRysXyFKNUcopesLIfq@switchyard.proxy.rlwy.net:47164/railway"

python3 scripts/upload_incremental_to_railway.py combined_sales_incremental.csv
```

---

## Troubleshooting

### Error: "pymssql not installed"

```bash
pip3 install pymssql==2.2.11
```

### Error: "Cannot connect to Azure SQL"

**Option 1:** Use VS Code manual method instead (Method 2 above)

**Option 2:** Check firewall
- Verify your local IP is whitelisted in Azure SQL firewall
- Azure Portal → SQL databases → Shopfiy → Firewalls and virtual networks

### Error: "DATABASE_URL not set"

```bash
export DATABASE_URL="postgresql://postgres:JSKjhRNwAbpJWgRysXyFKNUcopesLIfq@switchyard.proxy.rlwy.net:47164/railway"
```

### Check Current Data Freshness

```bash
psql $DATABASE_URL -c "SELECT MAX(order_date), COUNT(*) FROM combined_sales;"
```

---

## After Upload - Test Product Queries

```bash
# Test category revenue query
curl -X POST "https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/query/natural-language?query=which+categories+have+the+highest+revenue" \
  -H "X-API-Key: e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31" \
  | python3 -m json.tool

# Should show updated revenue numbers with fresh data!
```

---

## Comparison: CSV Method vs Automated Sync

| Aspect | CSV Method | Automated Sync |
|--------|------------|----------------|
| **Works Now** | ✅ YES | ⏳ Needs testing |
| **Speed** | 5-10 minutes | Runs at 2 AM UTC |
| **Frequency** | Manual (as needed) | Daily (automatic) |
| **Requirements** | Local Azure SQL access | Railway IP whitelisted |
| **Best For** | One-time catch-up | Daily maintenance |

---

## Recommendation

**Today:** Use CSV method to catch up the 12 days of missing data

**Tomorrow:** Automated sync should work (IP is whitelisted, code is fixed)

**Going Forward:** Daily automated sync at 2 AM UTC will keep data fresh

---

## Summary

✅ **Quick Win:** CSV method works RIGHT NOW
✅ **No IP issues:** Runs from your local machine
✅ **Safe:** Uses APPEND mode (doesn't delete existing data)
✅ **Fast:** ~5-10 minutes total

**Next:** Run the export script to get the missing data!

```bash
# One command to get started:
python3 scripts/export_incremental_azure_to_csv.py
```
