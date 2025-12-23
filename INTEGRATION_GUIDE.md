# Quimbi Intelligence Backend - Integration Guide

## Overview

This guide explains how to integrate the Quimbi Intelligence Backend with your e-commerce platform. The Intelligence Backend provides customer behavioral clustering, segmentation, and AI-powered insights.

**Platform Agnostic**: Works with any hosting provider, database, and e-commerce platform.

---

## Prerequisites

### Required:
1. **SQL Database** - PostgreSQL, MySQL, or compatible RDBMS
2. **Python 3.11+** runtime environment
3. **E-commerce Platform** - Any source of customer/order data (Shopify, WooCommerce, Magento, custom, etc.)

### Optional (Performance):
- **Redis** - For caching (improves response times)
- **Anthropic API** - For AI-powered segment naming (can run without)

---

## Database Schema Requirements

The Intelligence Backend needs customer and order data. It works with your existing database or a separate analytics database.

### Core Tables Required

You can either:
- **A)** Use our schema (copy to your database)
- **B)** Map your existing tables (modify configuration)

#### Required Data Structure:

**1. Customers Table**
```sql
-- Table name: configurable (default: ecommerce.customers)
CREATE TABLE customers (
    id BIGINT PRIMARY KEY,           -- Your unique customer ID
    email VARCHAR(255),              -- Customer email
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    total_spent DECIMAL(10,2),       -- Lifetime spend
    orders_count INTEGER,            -- Total orders
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**2. Orders Table**
```sql
-- Table name: configurable (default: ecommerce.orders)
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    customer_id BIGINT,              -- Foreign key to customers
    order_number VARCHAR(50),
    total_price DECIMAL(10,2),
    created_at TIMESTAMP,
    financial_status VARCHAR(50),
    fulfillment_status VARCHAR(50)
);
```

**3. Order Line Items Table**
```sql
-- Table name: configurable (default: ecommerce.order_line_items)
CREATE TABLE order_line_items (
    id BIGINT PRIMARY KEY,
    order_id BIGINT,                 -- Foreign key to orders
    product_id BIGINT,
    product_title VARCHAR(255),
    quantity INTEGER,
    price DECIMAL(10,2),
    vendor VARCHAR(100)
);
```

**4. Customer Intelligence Table** (Auto-created by Intelligence Backend)
```sql
-- This table stores the clustering results
CREATE TABLE customer_intelligence (
    customer_id BIGINT PRIMARY KEY,
    archetype_id VARCHAR(100),       -- Segment identifier
    archetype_name VARCHAR(255),     -- Human-readable segment name
    archetype_level INTEGER,         -- Hierarchy level
    ltv DECIMAL(10,2),              -- Predicted lifetime value
    churn_risk DECIMAL(5,4),        -- Churn probability (0-1)
    cluster_confidence DECIMAL(5,4), -- Segment fit score
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Using Your Existing Schema

If you have existing tables with different names/structure, update the configuration:

```python
# backend/core/config.py or environment variables
CUSTOMERS_TABLE = "your_schema.your_customers_table"
ORDERS_TABLE = "your_schema.your_orders_table"
LINE_ITEMS_TABLE = "your_schema.your_line_items_table"
```

---

## Data Sync Strategy

The Intelligence Backend **reads** customer/order data. You need to populate the database with your e-commerce data.

### Sync Options:

#### Option 1: Direct Database Connection (Best for existing data)
Point the Intelligence Backend to your existing e-commerce database (read-only recommended).

#### Option 2: ETL Pipeline (Best for separation)
Create a sync script that copies data from your e-commerce platform to an analytics database.

**Example sync script:**
```python
import asyncpg
from your_ecommerce_api import get_customers, get_orders

async def sync_data():
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Sync customers
    customers = get_customers()  # From Shopify/WooCommerce/etc.
    for customer in customers:
        await conn.execute("""
            INSERT INTO customers (id, email, first_name, total_spent, orders_count)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE SET
                total_spent = EXCLUDED.total_spent,
                orders_count = EXCLUDED.orders_count
        """, customer.id, customer.email, ...)
    
    await conn.close()
```

**Sync Frequency Recommendations:**
- **Real-time** - High-value customer updates (via webhooks)
- **Hourly** - Order data
- **Daily** - Full customer base refresh

---

## Deployment

### Environment Variables

```bash
# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:port/database
# Or for MySQL: mysql://user:pass@host:port/database

# API Authentication (REQUIRED)
API_KEY=your-secret-api-key-here

# AI Features (OPTIONAL)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Cache (OPTIONAL - improves performance)
REDIS_URL=redis://host:6379/0

# Feature Flags (OPTIONAL)
ENABLE_DYNAMIC_K_RANGE=true
CLUSTERING_ROBUST_SCALING=true
```

### Deployment Options

#### Option A: Docker (Any Platform)

```dockerfile
# Use provided Dockerfile
docker build -t intelligence-backend .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e API_KEY=your-key \
  intelligence-backend
```

#### Option B: Cloud Platform (Railway, Render, Heroku, AWS, etc.)

**Railway:**
```bash
# Auto-detects Python/FastAPI
railway up
```

**Render/Heroku:**
```bash
# Uses Procfile or detects uvicorn
git push heroku main
```

**AWS/GCP/Azure:**
- Deploy as Container (ECS, Cloud Run, App Service)
- Or as Function (Lambda, Cloud Functions, Azure Functions)

#### Option C: Traditional Server (VPS, Bare Metal)

```bash
# Install dependencies
pip install -r requirements.txt

# Run with systemd/supervisor
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**systemd service example:**
```ini
[Unit]
Description=Intelligence Backend
After=network.target

[Service]
Type=simple
User=www-data
Environment="DATABASE_URL=postgresql://..."
Environment="API_KEY=your-key"
ExecStart=/usr/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## API Endpoints

All endpoints require authentication via `X-API-Key` header.

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
  "customer_id": "12345",
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

**Search Customers**
```bash
GET /api/mcp/customers/search?query=john&limit=10
Headers:
  X-API-Key: your-api-key
```

**Get All Segments**
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

### Clustering & Analysis

**Trigger Clustering Analysis**
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

This runs behavioral clustering on your customer base and updates the `customer_intelligence` table.

---

## Integration Examples

### Example 1: E-commerce Platform Integration

```python
# In your e-commerce application
import httpx

async def get_customer_insights(customer_id: str):
    """Fetch intelligence for personalized experiences"""
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{INTELLIGENCE_API_URL}/api/mcp/customers/{customer_id}",
            headers={"X-API-Key": API_KEY}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Business logic based on intelligence
            if data['churn_risk'] > 0.7:
                # High churn risk - send retention offer
                trigger_winback_campaign(customer_id)
            
            if data['ltv'] > 1000:
                # High value - offer premium perks
                upgrade_to_vip(customer_id)
            
            return data
```

### Example 2: Product Recommendations

```python
async def get_segment_recommendations(customer_id: str):
    """Get product recommendations based on segment behavior"""
    
    # Get customer's segment
    customer = await get_customer_insights(customer_id)
    archetype_id = customer['archetype']['id']
    
    # Query database for segment trends
    async with database.acquire() as conn:
        products = await conn.fetch("""
            SELECT 
                ol.product_title,
                COUNT(*) as purchase_count,
                AVG(ol.price) as avg_price
            FROM order_line_items ol
            JOIN orders o ON ol.order_id = o.id
            JOIN customer_intelligence ci ON o.customer_id = ci.customer_id
            WHERE ci.archetype_id = $1
              AND o.created_at > NOW() - INTERVAL '90 days'
            GROUP BY ol.product_title
            ORDER BY purchase_count DESC
            LIMIT 10
        """, archetype_id)
    
    return products
```

### Example 3: Automated Campaigns

```python
async def identify_campaign_targets():
    """Find customers for targeted campaigns"""
    
    # Get all segments
    response = await httpx.get(
        f"{INTELLIGENCE_API_URL}/api/mcp/segments",
        headers={"X-API-Key": API_KEY}
    )
    
    segments = response.json()['segments']
    
    for segment in segments:
        if segment['avg_ltv'] > 2000 and segment['customer_count'] > 100:
            # High-value segment - create VIP campaign
            create_vip_campaign(segment['id'])
        
        elif segment.get('churn_risk_avg', 0) > 0.6:
            # At-risk segment - create retention campaign
            create_retention_campaign(segment['id'])
```

---

## Monitoring & Maintenance

### Health Monitoring

```bash
# Check API health
curl https://your-api.com/health

# Check clustering status
curl -H "X-API-Key: your-key" https://your-api.com/api/admin/cluster/status
```

### Scheduled Tasks

Recommended cron jobs:

```bash
# Daily clustering update (adjust frequency based on data volume)
0 2 * * * curl -X POST https://your-api.com/api/admin/cluster \
  -H "X-API-Key: your-admin-key" \
  -d '{"sample_size": 1000}'

# Weekly full re-segmentation
0 3 * * 0 curl -X POST https://your-api.com/api/admin/cluster \
  -H "X-API-Key: your-admin-key" \
  -d '{"sample_size": 5000}'
```

---

## Performance Optimization

### Database Indexes (Critical)

```sql
-- Customer lookup performance
CREATE INDEX idx_customer_email ON customers(email);
CREATE INDEX idx_customer_created ON customers(created_at);

-- Order queries
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_created ON orders(created_at);
CREATE INDEX idx_line_items_order ON order_line_items(order_id);

-- Intelligence lookups
CREATE INDEX idx_intelligence_archetype ON customer_intelligence(archetype_id);
CREATE INDEX idx_intelligence_updated ON customer_intelligence(updated_at);
```

### Caching

1. **Enable Redis** - 10x faster response times for frequently accessed data
2. **Database connection pooling** - Configured automatically by asyncpg
3. **Sample-based clustering** - Start with 1000 customers, increase gradually

---

## Troubleshooting

### Database Connection Issues

```bash
# Test database connectivity
psql $DATABASE_URL -c "SELECT COUNT(*) FROM customers;"
# Or for MySQL:
mysql -h host -u user -p -e "SELECT COUNT(*) FROM customers;"
```

### Missing Intelligence Data

If customers don't have segment data:

```sql
-- Check if clustering has run
SELECT COUNT(*) FROM customer_intelligence;
```

If zero, trigger initial clustering:
```bash
curl -X POST https://your-api.com/api/admin/cluster \
  -H "X-API-Key: your-admin-key"
```

### Performance Issues

1. **Add database indexes** (see Performance Optimization section)
2. **Enable Redis caching**
3. **Reduce sample size** - Start with 1000, increase gradually
4. **Check database query performance**:
```sql
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 123;
```

---

## Architecture

```
┌─────────────────────────────────────┐
│   Your E-commerce Platform          │
│   (Shopify/WooCommerce/Custom)      │
└────────────┬────────────────────────┘
             │ Data Sync (your ETL)
             ▼
┌─────────────────────────────────────┐
│   Database (PostgreSQL/MySQL)       │
│   - customers                       │
│   - orders                          │
│   - order_line_items                │
│   - customer_intelligence (output)  │
└────────────┬────────────────────────┘
             │ SQL Queries
             ▼
┌─────────────────────────────────────┐
│   Intelligence Backend              │
│   - Behavioral Clustering           │
│   - Segment Analysis                │
│   - LTV Prediction                  │
│   - Churn Risk Scoring              │
└────────────┬────────────────────────┘
             │ REST API
             ▼
┌─────────────────────────────────────┐
│   Your Application                  │
│   - Personalization                 │
│   - Marketing Automation            │
│   - Customer Service                │
└─────────────────────────────────────┘
```

---

## Next Steps

1. ✅ Set up database (any SQL database)
2. ✅ Sync your customer/order data
3. ✅ Deploy Intelligence Backend (any platform)
4. ✅ Configure environment variables
5. ✅ Run initial clustering
6. ✅ Integrate API into your application
7. ✅ Set up monitoring and scheduled tasks

---

## Support & Documentation

- **API Documentation**: `https://your-api.com/docs` (Swagger UI)
- **Architecture Details**: See `/docs` directory
- **GitHub**: https://github.com/Quimbi-ai/intelligence-backend

**Platform agnostic - works with any infrastructure, database, or e-commerce platform.**
