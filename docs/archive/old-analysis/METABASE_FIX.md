# Metabase Deployment Fix

## Problem
Metabase is failing with: `database "metabase" does not exist`

This happens because Metabase needs **two separate databases**:
1. **Internal database** - stores Metabase's own config (dashboards, users, etc.)
2. **Data database** - your customer segmentation data (PostgreSQL on Railway)

The error occurs because we told Metabase to use PostgreSQL for its internal storage (`MB_DB_TYPE=postgres`), but there's no database named "metabase" available.

## Solution: Use H2 for Internal Storage

Remove the Metabase internal database configuration and let it use H2 (embedded file-based database). This is simpler and works great for single-instance deployments.

### Step 1: Update Railway Variables

Remove these variables (or set them to empty):
```bash
MB_DB_TYPE (remove this)
MB_DB_DBNAME (remove this)
MB_DB_PORT (remove this)
MB_DB_USER (remove this)
MB_DB_PASS (remove this)
MB_DB_HOST (remove this)
```

Keep only:
```bash
MB_SITE_NAME=Customer Segmentation Dashboard
```

### Step 2: Add Volume for Persistence

In Railway dashboard:
1. Go to your Metabase service
2. Click "Settings" → "Volumes"
3. Add volume:
   - Mount path: `/metabase-data`
   - Size: 1GB

### Step 3: Restart Metabase

Click "Deploy" or "Restart" in Railway.

Metabase will now:
- Use H2 database stored in `/metabase-data` for internal config
- Allow you to add your PostgreSQL database connection via UI

## Alternative: Create Separate Metabase Database

If you prefer PostgreSQL for internal storage:

### Create the database:
```bash
PGPASSWORD="JSKjhRNwAbpJWgRysXyFKNUcopesLIfq" psql \
  -h switchyard.proxy.rlwy.net \
  -p 47164 \
  -U postgres \
  -d railway \
  -c "CREATE DATABASE metabase;"
```

Then update Railway variables to use `MB_DB_DBNAME=metabase`

## Quick Fix via Railway CLI

```bash
# Option 1: Remove MB_DB variables (use H2)
railway variables delete MB_DB_TYPE
railway variables delete MB_DB_DBNAME
railway variables delete MB_DB_PORT
railway variables delete MB_DB_USER
railway variables delete MB_DB_PASS
railway variables delete MB_DB_HOST

# Restart
railway service restart metabase
```

## After Fix: Connect to Your Data

Once Metabase starts successfully:

1. Visit your Metabase URL
2. Complete initial setup (create admin account)
3. Add database connection:
   - **Type**: PostgreSQL
   - **Host**: `switchyard.proxy.rlwy.net`
   - **Port**: `47164`
   - **Database**: `railway`
   - **Username**: `postgres`
   - **Password**: `JSKjhRNwAbpJWgRysXyFKNUcopesLIfq`
4. Click "Save"
5. Follow [METABASE_DASHBOARD_BUILDER.md](docs/METABASE_DASHBOARD_BUILDER.md) to build dashboards

## Why This Happened

The original guide assumed you wanted PostgreSQL for everything. For single-instance Metabase, H2 is simpler and sufficient. Only use PostgreSQL for Metabase's internal storage if you need:
- High availability (multiple Metabase instances)
- Database replication
- Advanced backup strategies

For your use case (single dashboard instance), H2 is perfect.
