# Sync Troubleshooting - After IP Whitelist

**Date:** November 3, 2025
**Status:** IP whitelisted (162.220.232.99), testing sync

---

## IP Whitelist Status

✅ **WHITELISTED:** 162.220.232.99 (actual Railway static IP)
- Previous docs incorrectly listed: 162.220.232.163
- Correct IP now whitelisted in Azure SQL firewall

---

## Current Issue

**Problem:** Manual sync trigger returning generic error

**Command Attempted:**
```bash
curl -X POST "https://ecommerce-backend-staging-a14c.up.railway.app/admin/sync-sales?mode=incremental&admin_key=e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31"
```

**Response:**
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred. Please try again later."
  }
}
```

---

## Fix Applied

### Bug Fixed: Missing --incremental Flag

**Commit:** e626da4

**Problem:**
- Admin endpoint wasn't passing `--incremental` flag to sync script
- Script requires explicit flag, not implicit default

**Before:**
```python
elif mode == "dry-run":
    cmd.append("--dry-run")
# incremental has no flag (default)  ← WRONG!
```

**After:**
```python
elif mode == "incremental":
    cmd.append("--incremental")  ← FIXED!
elif mode == "dry-run":
    cmd.append("--dry-run")
```

---

## Next Steps to Test

### Option 1: Wait for Daily Scheduler (Recommended)

The scheduler runs daily at 2:00 AM UTC. Since IP is now whitelisted and code is fixed, the sync should work automatically tomorrow morning.

**Check after 2:00 AM UTC:**
```bash
psql $DATABASE_URL -c "SELECT MAX(order_date) as latest_order_date, COUNT(*) as total_rows FROM combined_sales;"
```

### Option 2: Check Railway Logs (If Accessible)

```bash
railway logs | grep -i "sync\|azure\|error"
```

Look for:
- ✅ "Connected to Azure SQL Server"
- ✅ "Synced X rows"
- ❌ Connection errors
- ❌ Authentication errors

### Option 3: Manual SSH/Shell Access

If you have Railway shell access:

```bash
# Set environment variables (should be automatic)
export AZURE_SQL_SERVER="linda.database.windows.net"
export AZURE_SQL_DATABASE="Shopfiy"
export AZURE_SQL_USERNAME="Quimby"
export AZURE_SQL_PASSWORD="+BZznTX7c"
export DATABASE_URL="postgresql://..."

# Run sync manually
python scripts/sync_combined_sales_simple.py --incremental

# Or dry-run test
python scripts/sync_combined_sales_simple.py --incremental --dry-run --limit 10
```

### Option 4: Test Connection Only

Create a simple test script to verify Azure SQL connectivity:

```python
import pymssql

conn = pymssql.connect(
    server='linda.database.windows.net',
    database='Shopfiy',
    user='Quimby',
    password='+BZznTX7c',
    port=1433,
    timeout=30
)

print("✅ Connected successfully!")
cursor = conn.cursor()
cursor.execute("SELECT TOP 1 * FROM vw_Combined_Sales")
row = cursor.fetchone()
print(f"✅ Can query data: {row}")
conn.close()
```

---

## Possible Issues

### Issue 1: pymssql Not Installed

**Symptom:** ImportError or module not found

**Check:**
```bash
pip list | grep pymssql
```

**Should show:**
```
pymssql==2.2.11
```

**Fix if missing:**
```bash
pip install pymssql==2.2.11
```

### Issue 2: IP Still Blocked

**Symptom:** Connection timeout or "Cannot connect to server"

**Verify Railway IP:**
```bash
curl ifconfig.me
# Should return: 162.220.232.99
```

**Verify Azure firewall:**
- Azure Portal → SQL databases → Shopfiy → Firewalls and virtual networks
- Check rule exists for 162.220.232.99

### Issue 3: Wrong Database/Credentials

**Symptom:** Authentication failed or database not found

**Check environment variables:**
```bash
echo $AZURE_SQL_SERVER      # Should be: linda.database.windows.net
echo $AZURE_SQL_DATABASE    # Should be: Shopfiy
echo $AZURE_SQL_USERNAME    # Should be: Quimby
```

### Issue 4: View Doesn't Exist

**Symptom:** "Invalid object name 'vw_Combined_Sales'"

**Check in Azure SQL:**
```sql
SELECT * FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_NAME = 'vw_Combined_Sales';
```

**If missing, create view:**
```bash
# Run: scripts/create_combined_sales_view.sql in Azure SQL
```

---

## Expected Behavior (When Working)

### Successful Dry-Run Output

```
2025-11-03 17:00:00 - INFO - Connecting to Azure SQL: linda.database.windows.net/Shopfiy
2025-11-03 17:00:01 - INFO - ✅ Connected to Azure SQL Server
2025-11-03 17:00:01 - INFO - Connecting to Railway Postgres...
2025-11-03 17:00:02 - INFO - ✅ Connected to Railway Postgres
2025-11-03 17:00:02 - INFO - 🔍 Finding last synced date...
2025-11-03 17:00:02 - INFO - Last synced order date: 2025-10-22
2025-11-03 17:00:02 - INFO - Querying Azure SQL for orders > 2025-10-22...
2025-11-03 17:00:05 - INFO - Found 15,432 new rows
2025-11-03 17:00:05 - INFO - 🏃 DRY RUN MODE - Would insert 15,432 rows
```

### Successful Incremental Sync Output

```
2025-11-03 17:00:00 - INFO - Connecting to Azure SQL: linda.database.windows.net/Shopfiy
2025-11-03 17:00:01 - INFO - ✅ Connected to Azure SQL Server
2025-11-03 17:00:01 - INFO - Connecting to Railway Postgres...
2025-11-03 17:00:02 - INFO - ✅ Connected to Railway Postgres
2025-11-03 17:00:02 - INFO - 🔍 Finding last synced date...
2025-11-03 17:00:02 - INFO - Last synced order date: 2025-10-22
2025-11-03 17:00:02 - INFO - Querying Azure SQL for orders > 2025-10-22...
2025-11-03 17:00:05 - INFO - Found 15,432 new rows
2025-11-03 17:00:05 - INFO - 📊 Inserting data to Railway Postgres...
2025-11-03 17:00:15 - INFO - ✅ Inserted 15,432 rows successfully
2025-11-03 17:00:15 - INFO - 📈 Total rows in combined_sales: 1,237,168
2025-11-03 17:00:15 - INFO - 🎉 Sync complete!
```

---

## Verification After Sync

### Check Data Freshness

```sql
SELECT
    MAX(order_date) as latest_order,
    COUNT(*) as total_rows,
    NOW() - MAX(order_date) as data_age
FROM combined_sales;
```

**Before sync:**
```
latest_order    | 2025-10-22 00:00:00
total_rows      | 1,221,736
data_age        | 12 days
```

**After successful sync:**
```
latest_order    | 2025-11-03 00:00:00  ← Should be recent!
total_rows      | 1,237,168            ← Should be higher!
data_age        | 0 days               ← Should be current!
```

### Test Product Query

```bash
curl -X POST "https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/query/natural-language?query=which+categories+have+the+highest+revenue" \
  -H "X-API-Key: e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31"
```

**Should return updated revenue numbers with fresh data!**

---

## Summary

| Status | Item |
|--------|------|
| ✅ | IP whitelisted (162.220.232.99) |
| ✅ | --incremental flag bug fixed (commit e626da4) |
| ✅ | Environment variables configured |
| ✅ | Scheduler enabled (runs 2 AM UTC) |
| ⏳ | Waiting for successful sync test |
| ⏳ | Manual trigger returning generic error (needs investigation) |

**Recommendation:**
1. Wait for tomorrow's scheduled sync (2 AM UTC)
2. Check data freshness in the morning
3. If still failing, need to access Railway logs or shell to see actual error

**Alternative:**
- If urgent, user with Railway access can SSH in and run sync manually to see actual error messages

---

**Next Update:** After scheduled sync runs (tomorrow morning after 2 AM UTC)
