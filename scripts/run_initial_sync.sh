#!/bin/bash
# ============================================================================
# Run Initial Full Sync from Azure SQL to Railway Postgres
# ============================================================================
# This script will:
# 1. Test connection to Azure SQL
# 2. Create combined_sales table in Postgres
# 3. Run a dry-run to preview data
# 4. Run full sync to load all historical data
# ============================================================================

set -e  # Exit on error

echo "============================================================================"
echo "🚀 Initial Azure SQL → Railway Postgres Sync"
echo "============================================================================"
echo ""

# Check if we're running in Railway environment
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL not set"
    echo "   Set Railway environment variable: DATABASE_URL"
    exit 1
fi

if [ -z "$AZURE_SQL_USERNAME" ]; then
    echo "❌ ERROR: Azure SQL credentials not set"
    echo "   Set these Railway environment variables:"
    echo "   - AZURE_SQL_SERVER"
    echo "   - AZURE_SQL_DATABASE"
    echo "   - AZURE_SQL_USERNAME"
    echo "   - AZURE_SQL_PASSWORD"
    exit 1
fi

echo "✅ Environment variables set"
echo ""

# Step 1: Test Azure SQL connection
echo "============================================================================"
echo "Step 1: Testing Azure SQL connection..."
echo "============================================================================"
echo ""

python scripts/test_azure_connection.py || {
    echo "❌ Azure SQL connection failed"
    exit 1
}

echo ""
echo "✅ Azure SQL connection successful"
echo ""

# Step 2: Preview data with dry-run
echo "============================================================================"
echo "Step 2: Preview data (dry-run - first 100 rows)..."
echo "============================================================================"
echo ""

python scripts/sync_combined_sales_simple.py --dry-run --limit 100 || {
    echo "❌ Dry-run failed"
    exit 1
}

echo ""
echo "✅ Dry-run successful - data looks good!"
echo ""

# Step 3: Confirm before full sync
echo "============================================================================"
echo "Step 3: Ready to run FULL SYNC"
echo "============================================================================"
echo ""
echo "This will:"
echo "  - Create combined_sales table in Postgres (if not exists)"
echo "  - Load ALL historical data from Azure SQL"
echo "  - May take 5-10 minutes depending on data size"
echo ""
read -p "Continue with full sync? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled by user"
    exit 0
fi

echo ""
echo "============================================================================"
echo "Running FULL SYNC..."
echo "============================================================================"
echo ""

python scripts/sync_combined_sales_simple.py --full || {
    echo "❌ Full sync failed"
    exit 1
}

echo ""
echo "============================================================================"
echo "✅ Initial sync complete!"
echo "============================================================================"
echo ""

# Step 4: Verify data
echo "============================================================================"
echo "Step 4: Verifying data..."
echo "============================================================================"
echo ""

# Count records
psql "$DATABASE_URL" -c "SELECT COUNT(*) as total_records FROM combined_sales;"

# Show date range
psql "$DATABASE_URL" -c "
SELECT
    MIN(order_date) as earliest_order,
    MAX(order_date) as latest_order,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT product_id) as unique_products,
    COUNT(DISTINCT order_id) as unique_orders
FROM combined_sales;
"

# Show sample records
psql "$DATABASE_URL" -c "
SELECT * FROM combined_sales
ORDER BY order_date DESC
LIMIT 5;
"

echo ""
echo "============================================================================"
echo "🎉 All done!"
echo "============================================================================"
echo ""
echo "Next steps:"
echo "  - Automatic incremental syncs will run daily at 2 AM UTC"
echo "  - Monitor in Railway logs"
echo "  - Query combined_sales table for analytics"
echo ""
echo "Manual sync commands:"
echo "  railway run python scripts/sync_combined_sales_simple.py --incremental"
echo "  railway run python scripts/sync_combined_sales_simple.py --start-date 2024-10-01"
echo ""
