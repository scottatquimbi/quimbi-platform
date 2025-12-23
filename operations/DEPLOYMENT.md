# Deployment Guide - Customer Intelligence Platform

**Complete guide for deploying the AI-powered customer segmentation system**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Environment](#development-environment)
3. [Staging Environment](#staging-environment)
4. [Production Environment](#production-environment)
5. [Database Strategy](#database-strategy)
6. [Caching Strategy](#caching-strategy)
7. [Discovery Jobs](#discovery-jobs)
8. [Monitoring & Alerts](#monitoring--alerts)
9. [Environment Variables](#environment-variables)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    E-COMMERCE PLATFORM                       │
│                    Customer Data Source                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Export customer data (CSV)
                         ↓
┌─────────────────────────────────────────────────────────────┐
│               DISCOVERY PIPELINE (Cron: 2x/day)              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. Load customer_profiles.csv (27K repeat customers) │   │
│  │ 2. Transform to 8 behavioral axes features           │   │
│  │ 3. Run KMeans clustering per axis (k=2-6)            │   │
│  │ 4. Generate fuzzy memberships (0.0-1.0)              │   │
│  │ 5. Count 869 Level 2 archetypes                      │   │
│  │ 6. Store to PostgreSQL/Redis                         │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                   PERSISTENCE LAYER                          │
│  ┌──────────────────────┐       ┌───────────────────────┐  │
│  │  PostgreSQL          │       │  Redis (Optional)     │  │
│  │  ─────────────────   │       │  ──────────────────   │  │
│  │  • customer_profiles │       │  • customer:<id>      │  │
│  │  • profile_history   │       │  • archetype:<id>     │  │
│  │  • archetypes        │       │  • segments:<axis>    │  │
│  │  • segments          │       │  TTL: 12 hours        │  │
│  └──────────────────────┘       └───────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                   MCP SERVER / API LAYER                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ FastAPI Application                                  │   │
│  │ ├─ /api/gorgias/ticket-created (webhook)            │   │
│  │ ├─ /api/mcp/* (6 tools)                             │   │
│  │ └─ /api/analytics/* (optional REST API)             │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    AI INTEGRATIONS                           │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │   Gorgias    │   │  Slack Bot   │   │  Marketing   │   │
│  │   Customer   │   │  Internal BI │   │  Automation  │   │
│  │   Support    │   │              │   │              │   │
│  └──────────────┘   └──────────────┘   └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Development Environment

**Purpose**: Local testing, debugging, rapid iteration

### Prerequisites

```bash
# Required
- Python 3.11-3.13
- Git

# Optional (can use in-memory/SQLite for testing)
- PostgreSQL 14+ (local or Docker)
- Redis 7+ (local or Docker)
```

### Setup

```bash
# 1. Clone repository
git clone https://github.com/Quimbi-ai/Ecommerce-backend.git
cd Ecommerce-backend

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env with your local settings

# 5. (Optional) Start local PostgreSQL
docker run --name ecommerce-postgres \
  -e POSTGRES_PASSWORD=dev_password \
  -e POSTGRES_DB=customer_segmentation \
  -p 5432:5432 \
  -d postgres:14

# 6. (Optional) Start local Redis
docker run --name ecommerce-redis \
  -p 6379:6379 \
  -d redis:7-alpine

# 7. Run migrations (if using PostgreSQL)
alembic upgrade head

# 8. Test with sample data
python scripts/quick_test_mcp.py
```

### Expected Output

```
================================================================================
QUICK MCP SERVER TEST - 1000 CUSTOMER SAMPLE
================================================================================

1. Loading customer data...
   ✅ Loaded 1000 customers

2. Running segmentation discovery...
   ✅ Discovered 33 segments across 8 axes

3. Generating customer profiles...
   ✅ Generated 1000 profiles, 363 archetypes

4. Loading into MCP server...
   ✅ MCP server ready

USE CASE 1: ANALYTICS - Business Intelligence Queries
...
```

### Development Workflow

```bash
# Run full discovery (takes ~5 minutes)
python scripts/load_linda_data.py

# Sync to local PostgreSQL
python scripts/sync_profiles_to_db.py --rediscover

# Start API server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Access API docs
open http://localhost:8000/docs
```

### Data Strategy: Development

**Option A: In-Memory (Fastest for testing)**
```python
# mcp_server/segmentation_server.py already uses this
data_store = SegmentationDataStore()  # Dict-based, no persistence
```
- ✅ Zero setup
- ✅ Fast (<1ms lookups)
- ❌ Lost on restart
- ❌ Can't scale horizontally

**Option B: SQLite (Good middle ground)**
```bash
# .env
DATABASE_URL=sqlite:///./linda_dev.db
```
- ✅ Persists across restarts
- ✅ No server setup
- ❌ No concurrent writes
- ❌ Limited JSONB support

**Option C: PostgreSQL (Production-like)**
```bash
# .env
DATABASE_URL=postgresql://postgres:dev_password@localhost:5432/customer_segmentation
```
- ✅ Full JSONB support
- ✅ Production parity
- ❌ Requires PostgreSQL running

**Recommendation**: Start with Option A (in-memory), move to Option C when testing integrations.

---

## Staging Environment

**Purpose**: Pre-production testing, client demos, integration testing

### Infrastructure

**Recommended: Railway.app**

```yaml
# railway.toml
[build]
  builder = "NIXPACKS"
  buildCommand = "pip install -r requirements.txt"

[deploy]
  startCommand = "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
  healthcheckPath = "/health"
  healthcheckTimeout = 100
  restartPolicyType = "ON_FAILURE"
  restartPolicyMaxRetries = 10

[env]
  ENV = "staging"
  PYTHONUNBUFFERED = "1"
```

### Setup on Railway

```bash
# 1. Install Railway CLI
brew install railway  # or: npm install -g @railway/cli

# 2. Login
railway login

# 3. Create new project
railway init

# 4. Add PostgreSQL service
railway add postgresql

# 5. (Optional) Add Redis service
railway add redis

# 6. Set environment variables
railway variables set ENV=staging
railway variables set OPENAI_API_KEY=sk-...
railway variables set GORGIAS_WEBHOOK_SECRET=your_secret

# 7. Deploy
railway up

# 8. Run migrations
railway run alembic upgrade head

# 9. Load discovery data
railway run python scripts/sync_profiles_to_db.py --rediscover
```

### Staging Environment Variables

```bash
ENV=staging
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Auto-provided by Railway
REDIS_URL=${{Redis.REDIS_URL}}           # Auto-provided by Railway
PORT=${{PORT}}                            # Auto-provided by Railway

# API Keys
OPENAI_API_KEY=sk-...
GORGIAS_API_KEY=...
GORGIAS_WEBHOOK_SECRET=...

# Features
ENABLE_GORGIAS_WEBHOOK=true
ENABLE_CHURN_PREDICTION=true
ENABLE_REDIS_CACHE=true

# Logging
LOG_LEVEL=INFO
SENTRY_DSN=https://...  # Optional error tracking
```

### Data Strategy: Staging

**PostgreSQL + Redis (Recommended)**

```python
# backend/services/segmentation_service.py

class SegmentationService:
    def __init__(self):
        self.db = get_postgres_session()
        self.redis = redis.from_url(os.getenv("REDIS_URL"))

    async def get_customer_profile(self, customer_id: str):
        # Try Redis cache first
        cached = self.redis.get(f"customer:{customer_id}")
        if cached:
            return json.loads(cached)

        # Fallback to PostgreSQL
        profile = await self.db.query_customer_profile(customer_id)

        # Warm cache (12 hour TTL)
        self.redis.setex(f"customer:{customer_id}", 43200, json.dumps(profile))

        return profile
```

**Why both?**
- Redis: Fast reads (<1ms) for Gorgias webhooks
- PostgreSQL: Source of truth, complex queries, historical data

### Discovery Job: Staging

```bash
# Railway Cron Jobs (in project settings)

# Job 1: Morning discovery (6 AM PST)
Name: morning-discovery
Schedule: 0 14 * * *  # 6 AM PST = 14:00 UTC
Command: python scripts/sync_profiles_to_db.py --rediscover

# Job 2: Evening discovery (6 PM PST)
Name: evening-discovery
Schedule: 0 2 * * *   # 6 PM PST = 02:00 UTC (next day)
Command: python scripts/sync_profiles_to_db.py --rediscover
```

### Testing Gorgias Integration

```bash
# 1. Set up ngrok tunnel (for local testing)
ngrok http 8000

# 2. Configure Gorgias webhook (in Gorgias admin)
Webhook URL: https://your-app.railway.app/api/gorgias/ticket-created
# OR for local: https://abc123.ngrok.io/api/gorgias/ticket-created

# 3. Test webhook
curl -X POST https://your-app.railway.app/api/gorgias/ticket-created \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GORGIAS_WEBHOOK_SECRET" \
  -d '{
    "ticket_id": "test_123",
    "customer_id": "5971333382399",
    "customer_email": "test@example.com",
    "subject": "Wrong item in order",
    "messages": [{"body": "I received the wrong batting"}]
  }'

# Expected: 200 OK with AI response
```

---

## Production Environment

**Purpose**: Live customer-facing system

### Infrastructure Options

**Option 1: Railway (Recommended - Simplest)**

- ✅ Auto-scaling
- ✅ Built-in PostgreSQL + Redis
- ✅ Cron jobs included
- ✅ Free tier: $5/month credit
- ✅ Easy rollbacks

**Option 2: Render**

- ✅ Similar to Railway
- ✅ Better free tier for databases
- ❌ Cron jobs require paid plan

**Option 3: AWS (Most Control)**

- ✅ Full control
- ✅ Best for high scale (>10K tickets/day)
- ❌ More complex setup
- ❌ Higher cost

**Recommendation**: Start with Railway, migrate to AWS if you hit scale limits.

### Production Setup (Railway)

```bash
# 1. Create production project
railway init --name linda-prod

# 2. Add services
railway add postgresql   # Production database
railway add redis        # Cache layer

# 3. Set production variables
railway variables set ENV=production
railway variables set LOG_LEVEL=WARNING
railway variables set SENTRY_DSN=https://...

# 4. Deploy
railway up --environment production

# 5. Run migrations
railway run --environment production alembic upgrade head

# 6. Initial data load
railway run --environment production python scripts/sync_profiles_to_db.py --rediscover

# 7. Set up domain (optional)
railway domain
```

### Production Environment Variables

```bash
# Environment
ENV=production
DEBUG=false
LOG_LEVEL=WARNING

# Database (auto-provided by Railway)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
PORT=${{PORT}}

# API Keys
OPENAI_API_KEY=sk-prod-...
GORGIAS_API_KEY=prod-...
GORGIAS_WEBHOOK_SECRET=...

# Security
API_KEY_REQUIRED=true
API_KEY_HEADER=X-API-Key
ALLOWED_ORIGINS=https://linda.myshopify.com,https://app.gorgias.com

# Features
ENABLE_GORGIAS_WEBHOOK=true
ENABLE_CHURN_PREDICTION=true
ENABLE_REDIS_CACHE=true
REDIS_CACHE_TTL=43200  # 12 hours

# Monitoring
SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# Discovery
DISCOVERY_SCHEDULE_ENABLED=true
DISCOVERY_MIN_CUSTOMERS=1000  # Safety check
```

### Data Strategy: Production

**PostgreSQL (Primary) + Redis (Cache)**

```
┌─────────────────────────────────┐
│   Gorgias Webhook               │
│   (100-1000 requests/day)       │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│   Redis Cache Layer             │
│   ─────────────────             │
│   customer:<id>    (12h TTL)    │ ← Hot path: <1ms
│   archetype:<id>   (12h TTL)    │
│   segments:<axis>  (12h TTL)    │
└────────┬────────────────────────┘
         │ Cache miss
         ↓
┌─────────────────────────────────┐
│   PostgreSQL                    │
│   ─────────────────             │
│   customer_profiles             │ ← Source of truth
│   customer_profile_history      │ ← Historical snapshots
│   archetype_definitions         │ ← AI context
└─────────────────────────────────┘
         ↑
         │ Update 2x/day
         │
┌─────────────────────────────────┐
│   Discovery Cron Job            │
│   ─────────────────             │
│   6 AM & 6 PM PST               │
│   - Run clustering              │
│   - Update PostgreSQL           │
│   - Flush Redis cache           │
└─────────────────────────────────┘
```

### Scaling Considerations

**At 100 tickets/day**: PostgreSQL only is fine
**At 1,000 tickets/day**: Add Redis cache
**At 10,000 tickets/day**: Consider:
- Read replicas for PostgreSQL
- Multiple API instances (horizontal scaling)
- CDN for static assets
- Move to AWS/GCP for better autoscaling

---

## Database Strategy

### PostgreSQL Schema

```sql
-- Core customer profiles (current state)
CREATE TABLE customer_profiles (
    customer_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    segment_memberships JSONB NOT NULL,      -- {axis: {segment: membership}}
    dominant_segments JSONB NOT NULL,        -- {axis: segment_name}
    membership_strengths JSONB NOT NULL,     -- {axis: "strong"|"balanced"|"weak"}
    feature_vectors JSONB NOT NULL,          -- Raw features for re-clustering
    churn_risk_score REAL,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Historical snapshots for trend analysis
CREATE TABLE customer_profile_history (
    id SERIAL PRIMARY KEY,
    customer_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    days_ago INTEGER NOT NULL,               -- 7, 14, or 28
    segment_memberships JSONB NOT NULL,
    dominant_segments JSONB NOT NULL,
    membership_strengths JSONB NOT NULL,
    churn_risk_score REAL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(customer_id, snapshot_date, days_ago)
);

-- Archetype definitions (for AI context)
CREATE TABLE archetype_definitions (
    archetype_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    member_count INTEGER NOT NULL,
    population_percentage REAL NOT NULL,
    dominant_segments JSONB NOT NULL,
    strength_signature JSONB NOT NULL,
    average_ltv REAL,
    total_revenue REAL,
    average_orders REAL,
    business_description TEXT,               -- Human-readable description
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Discovered segments (per axis)
CREATE TABLE discovered_segments (
    id SERIAL PRIMARY KEY,
    store_id TEXT NOT NULL,
    axis_name TEXT NOT NULL,
    segment_name TEXT NOT NULL,
    centroid JSONB NOT NULL,                 -- Feature centroid
    member_count INTEGER NOT NULL,
    silhouette_score REAL,
    interpretation TEXT,
    discovery_run_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(store_id, axis_name, segment_name, discovery_run_id)
);

-- Indexes
CREATE INDEX idx_customer_profiles_store ON customer_profiles(store_id);
CREATE INDEX idx_customer_profiles_updated ON customer_profiles(last_updated);
CREATE INDEX idx_customer_profiles_segments ON customer_profiles USING GIN (segment_memberships);

CREATE INDEX idx_profile_history_customer ON customer_profile_history(customer_id, snapshot_date);
CREATE INDEX idx_profile_history_store ON customer_profile_history(store_id, days_ago);

CREATE INDEX idx_archetypes_store ON archetype_definitions(store_id);
CREATE INDEX idx_archetypes_size ON archetype_definitions(member_count DESC);
```

### Migrations

```bash
# Create new migration
alembic revision -m "add customer profiles tables"

# Run migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current version
alembic current
```

---

## Caching Strategy

### Redis Key Structure

```
# Customer profiles
customer:<customer_id>              → JSON profile (TTL: 12h)
customer:<customer_id>:churn        → Churn risk score (TTL: 12h)

# Archetypes
archetype:<archetype_id>            → Archetype stats (TTL: 12h)
archetype:list:<store_id>           → List of all archetypes (TTL: 12h)

# Segments
segments:<axis_name>                → List of segments for axis (TTL: 12h)
segments:<axis_name>:<segment_name> → Segment details (TTL: 12h)

# Search results (optional - for frequently accessed queries)
search:<filter_hash>                → Search results (TTL: 1h)
```

### Cache Invalidation

```python
# backend/services/cache_manager.py

class CacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def invalidate_all(self):
        """Called after discovery run completes"""
        # Flush all customer/archetype/segment keys
        pattern = "customer:*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

        # Same for archetypes and segments
        self.redis.delete(*self.redis.keys("archetype:*"))
        self.redis.delete(*self.redis.keys("segments:*"))

    async def invalidate_customer(self, customer_id: str):
        """Called when single customer updated"""
        self.redis.delete(f"customer:{customer_id}")
        self.redis.delete(f"customer:{customer_id}:churn")
```

### Cache Warming

```python
# scripts/warm_cache.py

async def warm_cache_after_discovery():
    """Pre-load hot customers into Redis after discovery"""

    # Get top 1000 customers by LTV (most likely to contact support)
    top_customers = db.query("""
        SELECT customer_id, segment_memberships, dominant_segments, ...
        FROM customer_profiles
        ORDER BY (feature_vectors->>'lifetime_value')::numeric DESC
        LIMIT 1000
    """)

    # Load into Redis
    for customer in top_customers:
        redis.setex(
            f"customer:{customer['customer_id']}",
            ttl=43200,  # 12 hours
            value=json.dumps(customer)
        )

    print(f"✅ Warmed cache with {len(top_customers)} top customers")
```

---

## Discovery Jobs

### Cron Schedule

**Recommended: 2x per day** (6 AM and 6 PM PST)

**Why twice daily?**
- E-commerce data changes slowly (not real-time)
- Clustering is expensive (~5 minutes for 27K customers)
- Gives support agents updated context twice daily
- Aligns with peak support hours

**Cron Expressions**:
```bash
# 6 AM PST = 14:00 UTC (or 13:00 UTC in DST)
0 14 * * *

# 6 PM PST = 02:00 UTC next day (or 01:00 UTC in DST)
0 2 * * *
```

### Discovery Script

```python
# scripts/scheduled_discovery.py

import asyncio
from datetime import datetime
from scripts.load_linda_data import run_discovery
from scripts.sync_profiles_to_db import sync_to_database
from backend.services.cache_manager import CacheManager

async def main():
    print(f"[{datetime.now()}] Starting scheduled discovery...")

    # 1. Run discovery
    profiles, segments, archetypes = await run_discovery()
    print(f"✅ Discovery complete: {len(profiles)} profiles, {len(archetypes)} archetypes")

    # 2. Sync to PostgreSQL
    await sync_to_database(profiles, segments, archetypes)
    print(f"✅ Synced to database")

    # 3. Invalidate cache
    cache = CacheManager(redis_client)
    await cache.invalidate_all()
    print(f"✅ Cache invalidated")

    # 4. Warm cache with top customers
    await warm_cache_after_discovery()
    print(f"✅ Cache warmed")

    # 5. Create snapshot (if 7/14/28 days)
    await maybe_create_snapshot()
    print(f"✅ Snapshot check complete")

    print(f"[{datetime.now()}] Scheduled discovery complete")

if __name__ == "__main__":
    asyncio.run(main())
```

### Railway Cron Setup

```bash
# In Railway dashboard:
# 1. Go to project → Settings → Cron Jobs
# 2. Add job:

Name: morning-discovery
Command: python scripts/scheduled_discovery.py
Schedule: 0 14 * * *
Environment: production

Name: evening-discovery
Command: python scripts/scheduled_discovery.py
Schedule: 0 2 * * *
Environment: production
```

### Monitoring Discovery Jobs

```python
# backend/models/discovery_runs.py

class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id = Column(String, primary_key=True)
    store_id = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    status = Column(String)  # running, completed, failed
    customers_processed = Column(Integer)
    archetypes_generated = Column(Integer)
    error_message = Column(Text)

    # Store metrics
    clustering_time_seconds = Column(Float)
    database_sync_time_seconds = Column(Float)
    cache_warm_time_seconds = Column(Float)
```

---

## Monitoring & Alerts

### Health Checks

```python
# backend/api/health.py

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@router.get("/health/ready")
async def readiness_check():
    """Check if service is ready to serve traffic"""

    # Check database connection
    try:
        db.execute("SELECT 1")
    except Exception as e:
        raise HTTPException(503, detail=f"Database unhealthy: {e}")

    # Check Redis (if enabled)
    if ENABLE_REDIS_CACHE:
        try:
            redis.ping()
        except Exception as e:
            raise HTTPException(503, detail=f"Redis unhealthy: {e}")

    return {"status": "ready"}

@router.get("/health/live")
async def liveness_check():
    """Check if service is alive (for k8s liveness probe)"""
    return {"status": "alive"}
```

### Metrics to Track

```python
# backend/services/metrics.py

class Metrics:
    # MCP tool performance
    mcp_tool_latency = Histogram("mcp_tool_latency_seconds", "MCP tool call latency")
    mcp_tool_calls = Counter("mcp_tool_calls_total", "Total MCP tool calls")

    # Gorgias webhook
    gorgias_webhook_latency = Histogram("gorgias_webhook_latency_seconds", "Webhook processing time")
    gorgias_webhook_errors = Counter("gorgias_webhook_errors_total", "Webhook errors")

    # Discovery jobs
    discovery_duration = Histogram("discovery_duration_seconds", "Discovery job duration")
    discovery_customers = Gauge("discovery_customers_processed", "Customers in last discovery")
    discovery_archetypes = Gauge("discovery_archetypes_generated", "Archetypes in last discovery")

    # Cache performance
    cache_hits = Counter("cache_hits_total", "Redis cache hits")
    cache_misses = Counter("cache_misses_total", "Redis cache misses")
```

### Alerts (Sentry/Email)

```python
# Important alerts to set up:

# 1. Discovery job failed
if discovery_status == "failed":
    sentry_sdk.capture_exception(error)
    send_alert("Discovery job failed", severity="critical")

# 2. Cache hit rate too low (<50%)
cache_hit_rate = cache_hits / (cache_hits + cache_misses)
if cache_hit_rate < 0.5:
    send_alert(f"Low cache hit rate: {cache_hit_rate:.2%}", severity="warning")

# 3. Database queries too slow (>100ms)
if query_time > 0.1:
    send_alert(f"Slow query: {query_time:.2f}s", severity="warning")

# 4. Gorgias webhook errors >5%
error_rate = webhook_errors / webhook_total
if error_rate > 0.05:
    send_alert(f"High webhook error rate: {error_rate:.2%}", severity="critical")
```

---

## Environment Variables

### Complete Reference

```bash
###################
# ENVIRONMENT
###################
ENV=development|staging|production
DEBUG=false
LOG_LEVEL=INFO|WARNING|ERROR

###################
# DATABASE
###################
DATABASE_URL=postgresql://user:pass@host:5432/dbname
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30

###################
# REDIS (Optional)
###################
REDIS_URL=redis://host:6379
REDIS_CACHE_TTL=43200           # 12 hours
ENABLE_REDIS_CACHE=true

###################
# API KEYS
###################
OPENAI_API_KEY=sk-...
GORGIAS_API_KEY=...
GORGIAS_WEBHOOK_SECRET=...

###################
# SECURITY
###################
API_KEY_REQUIRED=true
API_KEY_HEADER=X-API-Key
ALLOWED_ORIGINS=https://linda.myshopify.com,https://app.gorgias.com
CORS_ALLOW_CREDENTIALS=true

###################
# FEATURES
###################
ENABLE_GORGIAS_WEBHOOK=true
ENABLE_CHURN_PREDICTION=true
ENABLE_SLACK_BOT=false
ENABLE_PROACTIVE_OUTREACH=false

###################
# DISCOVERY
###################
DISCOVERY_SCHEDULE_ENABLED=true
DISCOVERY_MIN_CUSTOMERS=1000    # Safety check
DISCOVERY_MIN_K=2
DISCOVERY_MAX_K=6
DISCOVERY_MIN_SILHOUETTE=0.25
DISCOVERY_MIN_POPULATION=50

###################
# MONITORING
###################
SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

###################
# RATE LIMITING
###################
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

###################
# COMPENSATION ENGINE
###################
WHALE_LTV_THRESHOLD=10000       # $10K+
VIP_LTV_THRESHOLD=1000          # $1K+
HIGH_VALUE_LTV_THRESHOLD=500    # $500+
WHALE_DISCOUNT_PERCENT=25
VIP_DISCOUNT_PERCENT=20
HIGH_VALUE_DISCOUNT_PERCENT=15
REGULAR_DISCOUNT_PERCENT=10
```

---

## Troubleshooting

### Common Issues

#### 1. Discovery job times out

**Symptoms**: Cron job fails after 5+ minutes

**Solutions**:
```bash
# Option A: Increase timeout
railway config set RAILWAY_HEALTHCHECK_TIMEOUT=600

# Option B: Sample customers for faster discovery
python scripts/load_linda_data.py --sample-size 10000

# Option C: Run discovery less frequently (1x/day)
```

#### 2. Redis cache not working

**Symptoms**: All requests hit PostgreSQL, slow responses

**Check**:
```bash
# Verify Redis connection
railway run python -c "import redis; r = redis.from_url('$REDIS_URL'); print(r.ping())"

# Check cache keys
railway run redis-cli -u $REDIS_URL KEYS "customer:*" | head

# Test cache manually
railway run python scripts/test_redis_cache.py
```

**Fix**:
```bash
# Ensure ENABLE_REDIS_CACHE=true
railway variables set ENABLE_REDIS_CACHE=true

# Restart service
railway restart
```

#### 3. Gorgias webhook 500 errors

**Symptoms**: Tickets not getting AI responses

**Debug**:
```bash
# Check logs
railway logs --tail 100

# Test webhook locally
curl -X POST http://localhost:8000/api/gorgias/ticket-created \
  -H "Content-Type: application/json" \
  -d @test_ticket.json

# Check if customer exists
railway run python -c "
from mcp_server.segmentation_server import data_store
profile = data_store.customers.get('5971333382399')
print(profile if profile else 'Customer not found')
"
```

**Common fixes**:
- Customer not in database → Run discovery
- Invalid API key → Check GORGIAS_WEBHOOK_SECRET
- Missing features in profile → Check discovery completed successfully

#### 4. Database migrations fail

**Symptoms**: `alembic upgrade head` fails

**Solutions**:
```bash
# Check current version
railway run alembic current

# See pending migrations
railway run alembic heads

# Force to specific version
railway run alembic stamp head

# Re-run migration
railway run alembic upgrade head

# Nuclear option: reset database (CAREFUL!)
railway run alembic downgrade base
railway run alembic upgrade head
```

#### 5. Out of memory errors

**Symptoms**: Discovery crashes, API 502 errors

**Solutions**:
```bash
# Check memory usage
railway status

# Increase memory limit (Railway settings)
# Settings → Resources → Memory: 1GB → 2GB

# Or: Sample fewer customers
python scripts/load_linda_data.py --sample-size 10000

# Or: Use PostgreSQL instead of loading all into memory
ENABLE_REDIS_CACHE=false  # Fall back to PostgreSQL only
```

---

## Next Steps

1. **Choose environment** - Start with Development, move to Staging
2. **Set up infrastructure** - Railway project + PostgreSQL + Redis
3. **Deploy API** - FastAPI with MCP server
4. **Run initial discovery** - Load 27K customers
5. **Test Gorgias webhook** - Create test ticket
6. **Set up cron jobs** - 2x daily discovery
7. **Monitor metrics** - Sentry + Railway logs
8. **Go to production** - Switch Gorgias to production webhook

**See also**:
- [MCP_TOOLS.md](MCP_TOOLS.md) - MCP server tool documentation
- [GORGIAS_INTEGRATION.md](GORGIAS_INTEGRATION.md) - Gorgias setup guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture details

---

**Last Updated**: October 15, 2025
**Maintained By**: Scott Allen
