# Quimbi Intelligence Backend - Integration Guide

## Overview

This guide explains how to integrate the Quimbi Intelligence Backend with your e-commerce platform. The Intelligence Backend provides customer behavioral clustering, segmentation, and AI-powered insights.

---

## Prerequisites

### Required External Services:
1. **PostgreSQL Database** (v14+) - For storing customer and behavioral data
2. **E-commerce Platform** - Shopify, WooCommerce, etc. (data source)
3. **Optional: Redis** - For caching (improves performance)
4. **Optional: Anthropic API** - For AI-powered segment naming

---

## Database Schema Requirements

The Intelligence Backend requires specific database schemas. You have two options:

### Option A: Use Provided Schema (Recommended for New Deployments)

Run the migration scripts to create required schemas:

```bash
# Navigate to migrations directory
cd backend/database/migrations

# Connect to your PostgreSQL database
psql $DATABASE_URL

# Run schema creation
\i create_temporal_snapshots_schema.sql
```

### Option B: Map to Your Existing Schema

The Intelligence Backend expects these core tables in the `ecommerce` schema:

#### Required Tables:

**1. `ecommerce.customers`**
```sql
CREATE TABLE ecommerce.customers (
    id BIGINT PRIMARY KEY,           -- Unique customer ID
    email VARCHAR(255) UNIQUE,        -- Customer email
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    total_spent DECIMAL(10,2),        -- Lifetime value
    orders_count INTEGER,             -- Total orders placed
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**2. `ecommerce.orders`**
```sql
CREATE TABLE ecommerce.orders (
    id BIGINT PRIMARY KEY,
    customer_id BIGINT REFERENCES ecommerce.customers(id),
    order_number VARCHAR(50),
    total_price DECIMAL(10,2),
    created_at TIMESTAMP,
    financial_status VARCHAR(50),     -- 'paid', 'pending', etc.
    fulfillment_status VARCHAR(50)    -- 'fulfilled', 'unfulfilled'
);
```

**3. `ecommerce.order_line_items`**
```sql
CREATE TABLE ecommerce.order_line_items (
    id BIGINT PRIMARY KEY,
    order_id BIGINT REFERENCES ecommerce.orders(id),
    product_id BIGINT,
    product_title VARCHAR(255),
    quantity INTEGER,
    price DECIMAL(10,2),
    vendor VARCHAR(100)
);
```

**4. `ecommerce.customer_intelligence` (Created by Intelligence Backend)**
```sql
CREATE TABLE ecommerce.customer_intelligence (
    customer_id BIGINT PRIMARY KEY REFERENCES ecommerce.customers(id),
    archetype_id VARCHAR(100),        -- Behavioral segment ID
    archetype_name VARCHAR(255),      -- Human-readable segment name
    archetype_level INTEGER,          -- Hierarchy level
    ltv DECIMAL(10,2),               -- Lifetime value prediction
    churn_risk DECIMAL(5,4),         -- Churn probability (0-1)
    cluster_confidence DECIMAL(5,4), -- How well customer fits segment
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Data Sync Strategy

The Intelligence Backend **reads data** but **does not write to e-commerce tables**. You need a sync process to populate the database.

### Recommended Approach:

**Use a separate sync service** (like the included `azure-sync-cron` package):

```python
# Example sync script
import asyncpg
import shopify

async def sync_shopify_to_database():
    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Fetch customers from Shopify
    customers = shopify.Customer.find()
    
    for customer in customers:
        await conn.execute("""
            INSERT INTO ecommerce.customers (id, email, first_name, last_name, total_spent, orders_count, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                total_spent = EXCLUDED.total_spent,
                orders_count = EXCLUDED.orders_count,
                updated_at = NOW()
        """, customer.id, customer.email, ...)
    
    await conn.close()

# Run daily via cron
```

**Sync Frequency:**
- **Real-time**: For high-value customers (webhooks)
- **Hourly**: For order data
- **Daily**: For full customer sync

---

## API Endpoints

### Health Check
```bash
GET /health
```
Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "10.0"
}
```

---

### Customer Intelligence

**Get Customer Profile**
```bash
GET /api/mcp/customers/{customer_id}
Headers:
  X-API-Key: your-api-key
```

Response:
```json
{
  "customer_id": "7408502702335",
  "email": "customer@example.com",
  "archetype": {
    "id": "high_value_repeat",
    "name": "Loyal High Spenders",
    "level": 2
  },
  "ltv": 2450.00,
  "churn_risk": 0.12,
  "total_orders": 15,
  "avg_order_value": 163.33
}
```

---

**Search Customers**
```bash
GET /api/mcp/customers/search?query=john&limit=10
Headers:
  X-API-Key: your-api-key
```

---

**Get Customer Segments**
```bash
GET /api/mcp/segments
Headers:
  X-API-Key: your-api-key
```

Response:
```json
{
  "segments": [
    {
      "id": "high_value_repeat",
      "name": "Loyal High Spenders",
      "level": 2,
      "customer_count": 1247,
      "avg_ltv": 3200.00,
      "characteristics": {
        "recency_days": 15,
        "frequency": 12,
        "monetary_avg": 266.67
      }
    }
  ]
}
```

---

### Clustering & Segmentation

**Run Clustering**
```bash
POST /api/admin/cluster
Headers:
  X-API-Key: your-admin-key
Body:
{
  "sample_size": 1000,
  "min_k": 3,
  "max_k": 12
}
```

This triggers behavioral clustering analysis on your customer base.

---

## Environment Variables

Required configuration:

```bash
# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:port/dbname

# API Authentication (REQUIRED)
API_KEY=your-secret-api-key-here

# AI Segment Naming (OPTIONAL - improves segment descriptions)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Redis Cache (OPTIONAL - improves performance)
REDIS_URL=redis://localhost:6379/0

# Feature Flags
ENABLE_DYNAMIC_K_RANGE=true
CLUSTERING_ROBUST_SCALING=true
```

---

## Deployment on Railway

### Step 1: Create New Service

1. Go to Railway dashboard
2. Click "New Project" → "Deploy from GitHub"
3. Select your intelligence-backend repository
4. Railway will auto-detect FastAPI

### Step 2: Configure Environment

Add environment variables in Railway dashboard:

```
DATABASE_URL=postgresql://... (from Railway Postgres addon)
API_KEY=generate-secure-key-here
ANTHROPIC_API_KEY=sk-ant-... (optional)
```

### Step 3: Deploy

Railway will automatically:
- Build using `railway.json` config
- Install dependencies from `requirements.txt`
- Start with: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

### Step 4: Verify

```bash
curl https://your-app.railway.app/health
```

---

## Business Logic Integration

### Example: Get Customer Recommendations

```python
import httpx

async def get_customer_insights(customer_id: str):
    """Fetch customer intelligence for personalized experiences"""
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://intelligence-backend.railway.app/api/mcp/customers/{customer_id}",
            headers={"X-API-Key": INTELLIGENCE_API_KEY}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Use insights for business logic
            if data['churn_risk'] > 0.7:
                # Send retention email
                send_winback_campaign(customer_id)
            
            if data['ltv'] > 1000:
                # Offer VIP perks
                upgrade_to_vip(customer_id)
            
            return data
```

---

### Example: Product Recommendations

```python
async def get_segment_trends(archetype_id: str):
    """Get popular products for a customer segment"""
    
    # Query database for segment behavior
    async with database.acquire() as conn:
        products = await conn.fetch("""
            SELECT 
                ol.product_title,
                COUNT(*) as purchase_count,
                AVG(ol.price) as avg_price
            FROM ecommerce.order_line_items ol
            JOIN ecommerce.orders o ON ol.order_id = o.id
            JOIN ecommerce.customer_intelligence ci ON o.customer_id = ci.customer_id
            WHERE ci.archetype_id = $1
            GROUP BY ol.product_title
            ORDER BY purchase_count DESC
            LIMIT 10
        """, archetype_id)
    
    return products
```

---

## Monitoring & Maintenance

### Health Monitoring

```bash
# Check API health
curl -X GET https://your-backend.railway.app/health

# Check clustering status
curl -X GET https://your-backend.railway.app/api/admin/cluster/status \
  -H "X-API-Key: your-admin-key"
```

### Scheduled Tasks

Set up cron jobs for:

1. **Daily Clustering** (if data changes frequently)
```bash
0 2 * * * curl -X POST https://your-backend.railway.app/api/admin/cluster \
  -H "X-API-Key: your-admin-key"
```

2. **Weekly Full Re-segmentation**
```bash
0 3 * * 0 curl -X POST https://your-backend.railway.app/api/admin/cluster \
  -H "X-API-Key: your-admin-key" \
  -d '{"sample_size": 5000}'
```

---

## Troubleshooting

### Database Connection Issues

```bash
# Test database connectivity
psql $DATABASE_URL -c "SELECT COUNT(*) FROM ecommerce.customers;"
```

### Missing Customer Intelligence

If customers don't have intelligence data:

1. Check if clustering has run:
```sql
SELECT COUNT(*) FROM ecommerce.customer_intelligence;
```

2. Manually trigger clustering:
```bash
curl -X POST https://your-backend.railway.app/api/admin/cluster \
  -H "X-API-Key: your-admin-key"
```

### Performance Issues

1. **Enable Redis caching** - Reduces database load
2. **Increase sample size gradually** - Start with 1000 customers
3. **Use database indexes**:
```sql
CREATE INDEX idx_customer_email ON ecommerce.customers(email);
CREATE INDEX idx_orders_customer ON ecommerce.orders(customer_id);
CREATE INDEX idx_intelligence_archetype ON ecommerce.customer_intelligence(archetype_id);
```

---

## Next Steps

1. ✅ Set up database with required schemas
2. ✅ Deploy Intelligence Backend to Railway
3. ✅ Configure environment variables
4. ✅ Set up data sync from your e-commerce platform
5. ✅ Run initial clustering
6. ✅ Integrate API endpoints into your application
7. ✅ Set up monitoring and scheduled tasks

---

## Support

- **Documentation**: See `/docs` directory for detailed architecture
- **API Reference**: `https://your-backend.railway.app/docs` (Swagger UI)
- **GitHub**: https://github.com/Quimbi-ai/intelligence-backend
