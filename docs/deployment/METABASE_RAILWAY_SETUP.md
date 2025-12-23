# Metabase on Railway - Complete Setup Guide

## 🎯 Quick Answer: Environment Variables You Need

```bash
# Core Metabase Database Configuration
MB_DB_TYPE=postgres
MB_DB_DBNAME=railway
MB_DB_PORT=47164
MB_DB_USER=postgres
MB_DB_PASS=JSKjhRNwAbpJWgRysXyFKNUcopesLIfq
MB_DB_HOST=switchyard.proxy.rlwy.net

# Optional but Recommended
MB_SITE_NAME=Customer Segmentation Dashboard
MB_ADMIN_EMAIL=your-email@example.com
```

---

## 📋 Method 1: Railway Dashboard (Easiest)

### Step 1: Create New Service
1. Go to your Railway project
2. Click "+ New" → "Empty Service"
3. Name it "metabase"

### Step 2: Set Docker Image
1. In the service, click "Settings"
2. Under "Source", select "Deploy from Docker Image"
3. Enter: `metabase/metabase:latest`
4. Save

### Step 3: Add Environment Variables
Click "Variables" tab and add these **one by one**:

| Variable Name | Value |
|--------------|-------|
| `MB_DB_TYPE` | `postgres` |
| `MB_DB_DBNAME` | `railway` |
| `MB_DB_PORT` | `47164` |
| `MB_DB_USER` | `postgres` |
| `MB_DB_PASS` | `JSKjhRNwAbpJWgRysXyFKNUcopesLIfq` |
| `MB_DB_HOST` | `switchyard.proxy.rlwy.net` |
| `MB_SITE_NAME` | `Customer Segmentation Dashboard` |

### Step 4: Expose Port
1. Go to "Settings" → "Networking"
2. Click "Generate Domain" (Railway will create a public URL)
3. Note: Metabase runs on port 3000 internally (Railway auto-detects this)

### Step 5: Deploy
1. Railway will automatically deploy
2. Wait 2-3 minutes for container to start
3. Visit your generated domain (e.g., `https://metabase-production-xxxx.up.railway.app`)

---

## 📋 Method 2: Railway CLI (Faster)

### Prerequisites
```bash
# Install Railway CLI (if not already)
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link
```

### Deploy Metabase
```bash
# Create new service
railway service create metabase

# Switch to metabase service
railway service metabase

# Set all variables at once
railway variables set \
  MB_DB_TYPE=postgres \
  MB_DB_DBNAME=railway \
  MB_DB_PORT=47164 \
  MB_DB_USER=postgres \
  MB_DB_PASS=JSKjhRNwAbpJWgRysXyFKNUcopesLIfq \
  MB_DB_HOST=switchyard.proxy.rlwy.net \
  MB_SITE_NAME="Customer Segmentation Dashboard"

# Deploy from Docker image
railway up --detach --image metabase/metabase:latest

# Generate public domain
railway domain

# Check logs
railway logs
```

---

## 🔧 Initial Metabase Setup

### First Time Access

1. **Visit your Metabase URL**
   - Example: `https://metabase-production-xxxx.up.railway.app`
   - First load may take 30-60 seconds

2. **Welcome Screen**
   - Language: English
   - Click "Let's get started"

3. **Create Admin Account**
   - Email: `your-email@example.com`
   - Password: (choose a strong password)
   - First name: Your name
   - Company: Your company name

4. **Skip "Add your data" (Important!)**
   - Click "I'll add my data later"
   - Why? Your database is already configured via environment variables
   - Metabase is already using it for its application data

5. **Complete Setup**
   - Click through preferences
   - Finish setup wizard

---

## 🔌 Connect to Your Customer Data

Even though Metabase is using your PostgreSQL for its own data, you need to add it as a "data source" to query customer_profiles.

### Add Database Connection

1. **Click Settings Gear (top right) → Admin**
2. **Click "Databases" → "Add database"**
3. **Fill in connection details:**

```
Database type: PostgreSQL

Display name: Customer Segmentation DB
Host: switchyard.proxy.rlwy.net
Port: 47164
Database name: railway
Username: postgres
Password: JSKjhRNwAbpJWgRysXyFKNUcopesLIfq

SSL: Optional (leave default)
Additional JDBC connection string options: (leave blank)
```

4. **Click "Save"**
5. **Test connection** - should show "Connected successfully"

---

## 📊 Create Your First Dashboard

### Quick Dashboard Setup

1. **Click "New" → "Question"**
2. **Select "Customer Segmentation DB"**
3. **Choose "customer_profiles" table**

### Example Query 1: Segment Distribution
```sql
SELECT
    jsonb_object_keys(dominant_segments) as segment_axis,
    COUNT(*) as customer_count
FROM customer_profiles
WHERE dominant_segments <> '{}'
GROUP BY segment_axis
ORDER BY customer_count DESC
```

**Visualization:** Bar chart or Pie chart

### Example Query 2: LTV by Segment
```sql
SELECT
    dominant_segments->>'purchase_value' as value_segment,
    COUNT(*) as customers,
    AVG(lifetime_value) as avg_ltv,
    SUM(lifetime_value) as total_ltv
FROM customer_profiles
WHERE dominant_segments ? 'purchase_value'
GROUP BY value_segment
ORDER BY total_ltv DESC
```

**Visualization:** Table or Bar chart

### Save to Dashboard
1. Click "Save" on each question
2. Click "Yes please!" to add to dashboard
3. Create new dashboard: "Executive Overview"
4. Arrange charts as desired

---

## 🚨 Troubleshooting

### Issue: "Failed to connect to database"

**Solution 1:** Check if Railway PostgreSQL allows external connections
```bash
# Test connection from local machine
psql postgresql://postgres:JSKjhRNwAbpJWgRysXyFKNUcopesLIfq@switchyard.proxy.rlwy.net:47164/railway
```

**Solution 2:** Verify environment variables
```bash
railway logs --service metabase | grep "MB_DB"
```

**Solution 3:** Check if PostgreSQL is publicly accessible
- Railway → PostgreSQL service → Settings → Networking
- Ensure "Public Networking" is enabled

### Issue: "Metabase won't load"

**Check logs:**
```bash
railway logs --service metabase
```

**Common issues:**
- Port 3000 not exposed: Railway should auto-detect, but verify in Settings
- Out of memory: Upgrade Railway plan or reduce other services
- Database migration failed: Check PostgreSQL is accessible

### Issue: "Can't see customer_profiles table"

**Solution:** Metabase syncs schema periodically. Force sync:
1. Admin → Databases → Customer Segmentation DB
2. Click "Sync database schema now"
3. Wait 30 seconds
4. Refresh page

### Issue: Slow queries

**Add indexes to PostgreSQL:**
```sql
-- Connect to Railway PostgreSQL
psql postgresql://postgres:JSKjhRNwAbpJWgRysXyFKNUcopesLIfq@switchyard.proxy.rlwy.net:47164/railway

-- Add GIN indexes for JSONB columns
CREATE INDEX IF NOT EXISTS idx_dominant_segments
ON customer_profiles USING GIN (dominant_segments);

CREATE INDEX IF NOT EXISTS idx_segment_memberships
ON customer_profiles USING GIN (segment_memberships);

-- Add standard indexes
CREATE INDEX IF NOT EXISTS idx_lifetime_value
ON customer_profiles (lifetime_value);

CREATE INDEX IF NOT EXISTS idx_shop_id
ON customer_profiles (shop_id);
```

---

## 🎨 Pre-built Dashboard Templates

### Template 1: Executive Overview
```sql
-- KPI 1: Total Customers
SELECT COUNT(*) as total_customers FROM customer_profiles;

-- KPI 2: Segmentation Coverage
SELECT
    COUNT(*) FILTER (WHERE segment_memberships <> '{}')::float / COUNT(*) * 100 as coverage_pct
FROM customer_profiles;

-- KPI 3: Total LTV
SELECT SUM(lifetime_value) as total_ltv FROM customer_profiles;

-- Chart 1: Top 10 Segments
SELECT
    jsonb_object_keys(dominant_segments) as axis,
    dominant_segments->>jsonb_object_keys(dominant_segments) as segment,
    COUNT(*) as customers,
    AVG(lifetime_value) as avg_ltv
FROM customer_profiles
WHERE dominant_segments <> '{}'
GROUP BY axis, segment
ORDER BY customers DESC
LIMIT 10;
```

### Template 2: Marketing Dashboard
```sql
-- High-Value Segments
SELECT
    dominant_segments->>'purchase_value' as segment,
    COUNT(*) as customers,
    AVG(lifetime_value) as avg_ltv,
    SUM(lifetime_value) as total_revenue
FROM customer_profiles
WHERE dominant_segments ? 'purchase_value'
GROUP BY segment
ORDER BY total_revenue DESC;

-- Churn Risk by Segment
SELECT
    dominant_segments->>'customer_maturity' as maturity,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE churn_risk_score > 0.7) as high_risk,
    COUNT(*) FILTER (WHERE churn_risk_score > 0.7)::float / COUNT(*) * 100 as risk_pct
FROM customer_profiles
WHERE dominant_segments ? 'customer_maturity'
GROUP BY maturity
ORDER BY risk_pct DESC;
```

---

## ⚙️ Advanced Configuration

### Enable Email Alerts
```bash
# Add to Railway variables
MB_EMAIL_SMTP_HOST=smtp.gmail.com
MB_EMAIL_SMTP_PORT=587
MB_EMAIL_SMTP_USERNAME=your-email@gmail.com
MB_EMAIL_SMTP_PASSWORD=your-app-password
MB_EMAIL_SMTP_SECURITY=tls
```

### Increase Memory (if needed)
Railway → metabase service → Settings → Resources
- Increase memory limit if Metabase crashes
- Default 512MB usually sufficient for <100K customers

### Auto-refresh Dashboards
1. Edit dashboard
2. Click "⋯" menu → "Auto-refresh"
3. Set interval (e.g., 5 minutes)

### Public Sharing
1. Edit dashboard
2. Click "⋯" → "Sharing"
3. Enable "Public link"
4. Copy URL to share (no login required)

---

## 💰 Cost Breakdown

| Component | Cost |
|-----------|------|
| Metabase container | ~$5/month (Railway compute) |
| PostgreSQL | Already have ($0 extra) |
| Bandwidth | Included in Railway |
| **Total** | **~$5/month** |

**Free during Railway trial (first $5 free per month)**

---

## 🔐 Security Best Practices

1. **Change admin password** after first login
2. **Restrict IP access** (Railway Pro plan)
3. **Use read-only DB user** for Metabase queries:

```sql
-- Create read-only user
CREATE USER metabase_readonly WITH PASSWORD 'secure-password';
GRANT CONNECT ON DATABASE railway TO metabase_readonly;
GRANT USAGE ON SCHEMA public TO metabase_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO metabase_readonly;

-- Then use these credentials in Metabase connection
```

4. **Enable HTTPS** (Railway provides this automatically)
5. **Regular backups** of Metabase application database

---

## 📚 Next Steps

1. ✅ Deploy Metabase using Method 1 or 2
2. ✅ Complete initial setup
3. ✅ Add database connection
4. ✅ Create first dashboard using templates above
5. ✅ Share with team
6. ✅ Set up auto-refresh
7. ✅ Add email alerts (optional)

**Need help?**
- Railway Docs: https://docs.railway.app
- Metabase Docs: https://www.metabase.com/docs
- Check logs: `railway logs --service metabase`

