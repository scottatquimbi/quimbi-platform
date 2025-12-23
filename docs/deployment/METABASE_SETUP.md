# Metabase Dashboard Setup Guide

## Free Self-Hosted Metabase on Railway

Metabase is 100% free and open source when self-hosted. Don't use Metabase Cloud (which charges).

### Quick Deploy to Railway

#### Option 1: One-Click Deploy (Recommended)

1. **Deploy Metabase on Railway:**
   ```bash
   # In your Railway project
   railway add
   # Search for "metabase" in the template marketplace
   # Or use Docker image: metabase/metabase:latest
   ```

2. **Or via Railway Dashboard:**
   - Go to https://railway.app/
   - Click "+ New" → "Empty Service"
   - Click "Deploy" → "Docker Image"
   - Image: `metabase/metabase:latest`
   - Add port: `3000`

#### Option 2: Docker Compose (Local Testing)

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  metabase:
    image: metabase/metabase:latest
    ports:
      - "3000:3000"
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabase
      MB_DB_PORT: 5432
      MB_DB_USER: postgres
      MB_DB_PASS: your_password
      MB_DB_HOST: your_postgres_host
    volumes:
      - metabase-data:/metabase-data

volumes:
  metabase-data:
```

Run:
```bash
docker-compose up -d
```

Access at: http://localhost:3000

#### Option 3: Railway with Dockerfile

Create `Dockerfile.metabase`:
```dockerfile
FROM metabase/metabase:latest
EXPOSE 3000
```

Deploy:
```bash
railway up
```

### Initial Setup

1. **Access Metabase:**
   - Railway will give you a URL like `https://metabase-production-xxxx.up.railway.app`
   - Or local: `http://localhost:3000`

2. **First-time Setup Wizard:**
   - Choose language
   - Create admin account (email + password)
   - Skip "Add your data" for now

3. **Connect to Your PostgreSQL Database:**
   - Click "Settings" (gear icon) → "Admin" → "Databases" → "Add database"
   - Select "PostgreSQL"
   - Fill in your Railway PostgreSQL details:
     ```
     Name: Customer Segmentation DB
     Host: switchyard.proxy.rlwy.net
     Port: 47164
     Database name: railway
     Username: postgres
     Password: JSKjhRNwAbpJWgRysXyFKNUcopesLIfq
     ```
   - Click "Save"

### Create Your First Dashboard

#### Dashboard 1: Segment Overview

1. Click "New" → "Question"
2. Select your database → `customer_profiles` table
3. **Chart 1: Segment Distribution**
   - Visualization: Pie chart
   - Query:
     ```sql
     SELECT
       jsonb_object_keys(dominant_segments) as segment_axis,
       COUNT(*) as customer_count
     FROM customer_profiles
     WHERE dominant_segments <> '{}'
     GROUP BY segment_axis
     ```

4. **Chart 2: Top Segments by Customer Count**
   - Visualization: Bar chart
   - Query:
     ```sql
     SELECT
       jsonb_object_keys(dominant_segments) as axis,
       dominant_segments->>jsonb_object_keys(dominant_segments) as segment,
       COUNT(*) as customers
     FROM customer_profiles
     WHERE dominant_segments <> '{}'
     GROUP BY axis, segment
     ORDER BY customers DESC
     LIMIT 20
     ```

5. **Chart 3: Customer Value by Segment**
   - Visualization: Table
   - Query:
     ```sql
     SELECT
       dominant_segments->>'purchase_value' as value_segment,
       COUNT(*) as customers,
       AVG(lifetime_value) as avg_ltv,
       SUM(lifetime_value) as total_ltv
     FROM customer_profiles
     WHERE dominant_segments <> '{}'
     GROUP BY value_segment
     ORDER BY total_ltv DESC
     ```

#### Dashboard 2: Customer Health

```sql
-- Churn Risk Distribution
SELECT
  CASE
    WHEN churn_risk_score < 0.3 THEN 'Low Risk'
    WHEN churn_risk_score < 0.6 THEN 'Medium Risk'
    ELSE 'High Risk'
  END as risk_level,
  COUNT(*) as customers
FROM customer_profiles
WHERE churn_risk_score IS NOT NULL
GROUP BY risk_level
```

```sql
-- LTV by Customer Maturity
SELECT
  dominant_segments->>'customer_maturity' as maturity,
  COUNT(*) as customers,
  AVG(lifetime_value) as avg_ltv,
  AVG(total_orders) as avg_orders
FROM customer_profiles
WHERE dominant_segments <> '{}'
GROUP BY maturity
ORDER BY avg_ltv DESC
```

#### Dashboard 3: Behavioral Insights

```sql
-- Purchase Frequency vs Value
SELECT
  dominant_segments->>'purchase_frequency' as frequency_segment,
  dominant_segments->>'purchase_value' as value_segment,
  COUNT(*) as customers,
  AVG(lifetime_value) as avg_ltv
FROM customer_profiles
WHERE dominant_segments <> '{}'
GROUP BY frequency_segment, value_segment
ORDER BY customers DESC
```

### Useful Metabase Features

1. **Filters:** Add date filters, segment filters
2. **Auto-refresh:** Set dashboards to update every 5 minutes
3. **Alerts:** Get notifications when metrics change
4. **Sharing:** Share dashboards via public links or embed
5. **SQL Editor:** Write custom queries for deeper analysis

### Troubleshooting

**Can't connect to PostgreSQL:**
- Check Railway PostgreSQL is publicly accessible
- Verify credentials are correct
- Ensure Railway PostgreSQL plugin allows external connections

**Metabase slow:**
- Add indexes to `customer_profiles`:
  ```sql
  CREATE INDEX idx_dominant_segments ON customer_profiles USING GIN (dominant_segments);
  CREATE INDEX idx_segment_memberships ON customer_profiles USING GIN (segment_memberships);
  CREATE INDEX idx_lifetime_value ON customer_profiles (lifetime_value);
  ```

**Port not exposed:**
- Railway: Ensure port 3000 is exposed in service settings

### Cost Breakdown

- **Metabase**: $0 (open source)
- **Railway hosting**: $0 (free tier) or ~$5/month (hobby tier for more resources)
- **Total**: $0-5/month

### Alternative: Quick Streamlit Dashboard

If Railway setup is too complex, I can create a simple Streamlit dashboard that runs locally in 5 minutes.

### Next Steps

1. Deploy Metabase to Railway
2. Connect to your PostgreSQL database
3. Create 3 starter dashboards
4. Share with your team

Let me know if you hit any issues!
