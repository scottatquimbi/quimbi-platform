# Multi-Tenant Database Strategy: Database-Per-Company + Insights Aggregator

**Date**: 2025-11-24
**Model**: Complete data isolation with optional cross-company insights

---

## Core Principle

**Each company gets their own complete database. No shared tables. No cross-pollination.**

```
┌─────────────────────────────────────────────────────────────────┐
│  Company: Linda's Quilting                                      │
│  Database: linda_quilting                                       │
│                                                                 │
│  ├── platform schema                                            │
│  │   ├── customer_profiles (Linda's customers only)            │
│  │   ├── archetype_definitions (Linda's archetypes)            │
│  │   └── dim_archetype_l* (Linda's segments)                   │
│  │                                                              │
│  └── support_app schema                                         │
│      ├── tickets (Linda's tickets only)                        │
│      ├── agents (Linda's agents only)                          │
│      └── assignments (Linda's assignments only)                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Company: Outdoor Gear Co                                       │
│  Database: outdoor_gear                                         │
│                                                                 │
│  ├── platform schema                                            │
│  │   ├── customer_profiles (Outdoor's customers only)          │
│  │   ├── archetype_definitions (Outdoor's archetypes)          │
│  │   └── dim_archetype_l* (Outdoor's segments)                 │
│  │                                                              │
│  └── support_app schema                                         │
│      ├── tickets                                                │
│      ├── agents                                                 │
│      └── assignments                                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  INSIGHTS AGGREGATOR DATABASE (Separate)                        │
│  Database: quimbi_insights                                      │
│                                                                 │
│  ├── anonymized_behavioral_patterns                             │
│  │   └── No PII, no customer IDs, just patterns                │
│  │                                                              │
│  ├── industry_benchmarks                                        │
│  │   └── e.g., "retail churn averages 28% annually"            │
│  │                                                              │
│  ├── segment_effectiveness                                      │
│  │   └── "deal_hunter + high_ltv = 15% of base, 40% revenue"  │
│  │                                                              │
│  └── model_improvements                                         │
│      └── Aggregated training data for better models             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why This Model?

### ✅ Advantages

1. **True Data Isolation**
   - Linda's data never touches another company's database
   - Database-level security, not just application logic
   - Regulatory compliance easier (GDPR, CCPA, HIPAA if needed)

2. **Independent Scaling**
   - High-volume company gets bigger database instance
   - Low-volume company uses smaller/cheaper instance
   - Scale costs with customer value

3. **Custom Schemas per Company**
   - Linda might have custom fields (fabric types, quilt patterns)
   - Outdoor Gear might have custom fields (gear categories, seasons)
   - No schema compromises

4. **Disaster Isolation**
   - One company's database corruption doesn't affect others
   - Can restore one company without impacting others
   - Different backup/retention policies per company

5. **Data Sovereignty**
   - EU company's data in EU database
   - US company's data in US database
   - Meets data residency requirements

6. **Clear Exit Path**
   - Company leaves? Export their database and delete
   - No untangling from shared tables
   - Complete data portability

### ⚠️ Trade-offs

1. **More Databases to Manage**
   - Each company = new database instance
   - More connection strings, backups, migrations
   - **Mitigation**: Automate provisioning, use managed databases (Railway, AWS RDS)

2. **Cross-Company Queries Impossible**
   - Can't JOIN across companies (by design)
   - **Mitigation**: Use Insights Aggregator for benchmarking

3. **Schema Migration Complexity**
   - Need to migrate all company databases
   - **Mitigation**: Automated migration scripts, staged rollouts

4. **Higher Infrastructure Costs**
   - 10 companies = 10 database instances
   - **Mitigation**: Smaller instances for small customers, scale per need

---

## Database Provisioning Strategy

### Option 1: Separate PostgreSQL Instances (Maximum Isolation)

**Each company gets dedicated PostgreSQL instance:**

```yaml
# Railway services
linda-quilting-db:
  type: postgresql
  plan: starter  # $5/month for small company
  region: us-west

outdoor-gear-db:
  type: postgresql
  plan: pro  # $25/month for high-volume company
  region: us-west

craft-supplies-db:
  type: postgresql
  plan: starter
  region: eu-central  # European customer, EU data
```

**Pros:**
- ✅ Complete isolation (CPU, memory, disk)
- ✅ Independent scaling
- ✅ Independent backups
- ✅ Different regions possible

**Cons:**
- ⚠️ Most expensive option
- ⚠️ More management overhead

**When to use:** Regulatory requirements, high-value customers, different regions

---

### Option 2: Shared PostgreSQL Instance, Separate Databases (Recommended Start)

**One PostgreSQL instance, multiple databases:**

```yaml
# Railway service
quimbi-postgresql:
  type: postgresql
  plan: pro  # $25/month, shared across all companies
  databases:
    - linda_quilting
    - outdoor_gear
    - craft_supplies
```

**Connection strings:**
```
Linda:   postgresql://user:pass@host/linda_quilting
Outdoor: postgresql://user:pass@host/outdoor_gear
Craft:   postgresql://user:pass@host/craft_supplies
```

**Pros:**
- ✅ Cheaper (one instance for multiple companies)
- ✅ Easier to manage
- ✅ Still complete data isolation (different databases)
- ✅ Can't accidentally query wrong company

**Cons:**
- ⚠️ Share CPU/memory/disk resources
- ⚠️ One database failure affects all
- ⚠️ Can't scale per company
- ⚠️ All companies must be same region

**When to use:** MVP, early customers, cost-conscious, same geography

---

### Option 3: Hybrid (Start Shared, Split High-Value)

**Most companies share one instance, VIPs get dedicated:**

```yaml
# Shared instance for small customers
quimbi-postgresql-shared:
  databases: [linda_quilting, craft_supplies, small_co_1, small_co_2]

# Dedicated instance for high-volume customer
outdoor-gear-postgresql:
  dedicated: true
  plan: pro
```

**When to use:** Growing business with mix of customer sizes

---

## Application Architecture

### Tenant Resolution

**How the application knows which database to use:**

```python
# shared/database/tenant_resolver.py

import os
from typing import Dict

class TenantDatabaseResolver:
    """Resolves tenant to correct database connection."""

    def __init__(self):
        # Map tenant identifiers to database connection strings
        self.tenant_db_map = {
            "linda_quilting": os.getenv("LINDA_DB_URL"),
            "outdoor_gear": os.getenv("OUTDOOR_DB_URL"),
            "craft_supplies": os.getenv("CRAFT_DB_URL"),
        }

    def get_db_url(self, tenant_id: str) -> str:
        """Get database URL for tenant."""
        db_url = self.tenant_db_map.get(tenant_id)
        if not db_url:
            raise ValueError(f"No database configured for tenant: {tenant_id}")
        return db_url

    def get_async_engine(self, tenant_id: str):
        """Get SQLAlchemy async engine for tenant."""
        from sqlalchemy.ext.asyncio import create_async_engine

        db_url = self.get_db_url(tenant_id)
        return create_async_engine(
            db_url,
            pool_size=5,  # Per-tenant connection pool
            max_overflow=10,
            echo=False
        )


# Singleton
tenant_resolver = TenantDatabaseResolver()
```

### Request Flow

```python
# shared/middleware/tenant_routing.py

from starlette.middleware.base import BaseHTTPMiddleware
from shared.database.tenant_resolver import tenant_resolver
from shared.middleware.tenant_context import set_current_tenant

class TenantRoutingMiddleware(BaseHTTPMiddleware):
    """Identify tenant from request and set database context."""

    async def dispatch(self, request, call_next):
        # Identify tenant from:
        # 1. Subdomain (linda.quimbi.ai → linda_quilting)
        # 2. API key (lookup in shared tenant registry)
        # 3. JWT token (tenant_id claim)

        tenant_id = self._identify_tenant(request)

        if tenant_id:
            # Set tenant context for this request
            set_current_tenant(tenant_id)

            # Get tenant-specific database engine
            db_engine = tenant_resolver.get_async_engine(tenant_id)

            # Store in request state
            request.state.tenant_id = tenant_id
            request.state.db_engine = db_engine

        response = await call_next(request)
        return response

    def _identify_tenant(self, request) -> str:
        # Subdomain-based
        host = request.headers.get("host", "")
        if "linda.quimbi.ai" in host:
            return "linda_quilting"
        elif "outdoor.quimbi.ai" in host:
            return "outdoor_gear"

        # API key-based
        api_key = request.headers.get("x-api-key")
        if api_key:
            return self._lookup_tenant_by_api_key(api_key)

        # Default fallback (for development)
        return os.getenv("DEFAULT_TENANT_ID", "linda_quilting")
```

### Database Session per Tenant

```python
# shared/database/session.py

from contextvars import ContextVar
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Context variable to store current tenant's session factory
current_session_factory: ContextVar[async_sessionmaker] = ContextVar("session_factory")

async def get_db_session():
    """Get database session for current tenant."""
    from shared.middleware.tenant_context import get_current_tenant_id
    from shared.database.tenant_resolver import tenant_resolver

    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise RuntimeError("No tenant context set")

    # Get tenant-specific engine
    engine = tenant_resolver.get_async_engine(tenant_id)

    # Create session
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with session_factory() as session:
        yield session
```

### Usage in Endpoints

```python
# apps/support/api/routers/tickets.py

@router.get("/api/support/tickets")
async def list_tickets():
    """List tickets for current tenant."""
    # Middleware already set tenant context
    # Database session automatically uses correct tenant database

    async with get_db_session() as db:
        # This queries linda_quilting.support_app.tickets if tenant is Linda
        # Or outdoor_gear.support_app.tickets if tenant is Outdoor Gear
        result = await db.execute(
            select(Ticket).order_by(Ticket.created_at.desc())
        )
        tickets = result.scalars().all()
        return [t.to_dict() for t in tickets]
```

**Key point:** Application code doesn't know or care which database. Middleware handles it.

---

## Insights Aggregator Architecture

### Purpose

Build cross-company intelligence WITHOUT exposing individual company data.

### Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 1: Extract Anonymized Patterns (Per Company)              │
│                                                                  │
│  Linda's DB:                                                     │
│    • 10,000 customers                                            │
│    • Segment "deal_hunter + premium" = 15% of base, avg LTV $450│
│    • Churn rate: 22%                                            │
│                                                                  │
│  Outdoor's DB:                                                   │
│    • 50,000 customers                                            │
│    • Segment "deal_hunter + premium" = 12% of base, avg LTV $380│
│    • Churn rate: 31%                                            │
│                                                                  │
│  → NO customer PII, just aggregated statistics                  │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 2: Store in Insights Aggregator DB                        │
│                                                                  │
│  Table: segment_benchmarks                                       │
│  ┌─────────────┬───────────┬───────────┬──────────┬────────────┐│
│  │ industry    │ segment   │ companies │ avg_size │ avg_ltv    ││
│  ├─────────────┼───────────┼───────────┼──────────┼────────────┤│
│  │ retail      │ deal+prem │ 2         │ 13.5%    │ $415       ││
│  │ retail      │ loyal+hi  │ 2         │ 8%       │ $890       ││
│  └─────────────┴───────────┴───────────┴──────────┴────────────┘│
│                                                                  │
│  Table: industry_churn_benchmarks                                │
│  ┌─────────────┬───────────────┬──────────────┐                 │
│  │ industry    │ avg_churn     │ companies    │                 │
│  ├─────────────┼───────────────┼──────────────┤                 │
│  │ retail      │ 26.5%         │ 2            │                 │
│  └─────────────┴───────────────┴──────────────┘                 │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 3: Use Insights to Improve Individual Companies           │
│                                                                  │
│  Linda queries: "How does my churn compare to industry?"        │
│  Response: "Your churn (22%) is better than retail avg (26.5%)"│
│                                                                  │
│  Platform uses: Aggregate training data to improve ML models    │
│  Result: Better churn predictions for all companies             │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# platform/services/insights_aggregator.py

from typing import Dict, Any
from sqlalchemy import select, func
from datetime import datetime

class InsightsAggregator:
    """
    Aggregate anonymized insights across companies.

    CRITICAL: Never exposes individual customer data or company-specific details.
    Only statistical aggregates.
    """

    def __init__(self, insights_db_url: str):
        """
        Args:
            insights_db_url: Connection to separate insights database
        """
        from sqlalchemy.ext.asyncio import create_async_engine
        self.insights_engine = create_async_engine(insights_db_url)

    async def extract_company_patterns(self, tenant_id: str):
        """
        Extract anonymized patterns from ONE company's database.

        Called periodically (e.g., nightly) for each company.
        """
        from shared.database.tenant_resolver import tenant_resolver

        # Get tenant-specific database
        tenant_engine = tenant_resolver.get_async_engine(tenant_id)

        async with tenant_engine.connect() as conn:
            # Extract aggregated stats (NO individual customer data)
            result = await conn.execute("""
                SELECT
                    COUNT(*) as total_customers,
                    AVG(lifetime_value) as avg_ltv,
                    AVG(churn_risk_score) as avg_churn_risk,
                    -- Segment distribution
                    jsonb_object_agg(
                        archetype_id,
                        jsonb_build_object(
                            'count', count,
                            'avg_ltv', avg_segment_ltv
                        )
                    ) as segment_stats
                FROM (
                    SELECT
                        archetype_id,
                        COUNT(*) as count,
                        AVG(lifetime_value) as avg_segment_ltv
                    FROM platform.customer_profiles
                    GROUP BY archetype_id
                ) segments
                CROSS JOIN (
                    SELECT
                        COUNT(*) as total_customers,
                        AVG(lifetime_value) as avg_ltv,
                        AVG(churn_risk_score) as avg_churn_risk
                    FROM platform.customer_profiles
                ) totals
                GROUP BY total_customers, avg_ltv, avg_churn_risk
            """)

            patterns = result.fetchone()

        # Store in insights database (anonymized)
        await self._store_anonymized_patterns(tenant_id, patterns)

    async def _store_anonymized_patterns(
        self,
        tenant_id: str,
        patterns: Dict[str, Any]
    ):
        """
        Store patterns in insights DB.

        NOTE: We store tenant_id only to know which companies contributed,
        but all customer-level data is aggregated.
        """
        async with self.insights_engine.connect() as conn:
            await conn.execute("""
                INSERT INTO company_snapshots (
                    tenant_id,  -- For tracking contributors
                    snapshot_date,
                    total_customers,
                    avg_ltv,
                    avg_churn_risk,
                    segment_distribution,
                    -- NO customer IDs, NO PII
                )
                VALUES (:tenant_id, :date, :total, :ltv, :churn, :segments)
            """, {
                "tenant_id": tenant_id,
                "date": datetime.utcnow().date(),
                "total": patterns["total_customers"],
                "ltv": patterns["avg_ltv"],
                "churn": patterns["avg_churn_risk"],
                "segments": patterns["segment_stats"]
            })

    async def get_industry_benchmarks(self, industry: str = "retail") -> Dict:
        """
        Get cross-company benchmarks for an industry.

        Returns aggregated data only - no individual companies exposed.
        """
        async with self.insights_engine.connect() as conn:
            result = await conn.execute("""
                SELECT
                    COUNT(DISTINCT tenant_id) as companies_count,
                    AVG(avg_ltv) as industry_avg_ltv,
                    AVG(avg_churn_risk) as industry_avg_churn,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY avg_ltv) as ltv_p25,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY avg_ltv) as ltv_p50,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY avg_ltv) as ltv_p75
                FROM company_snapshots
                WHERE industry = :industry
                  AND snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
            """, {"industry": industry})

            benchmark = result.fetchone()

        return {
            "industry": industry,
            "based_on_companies": benchmark["companies_count"],
            "avg_ltv": benchmark["industry_avg_ltv"],
            "avg_churn": benchmark["industry_avg_churn"],
            "ltv_percentiles": {
                "p25": benchmark["ltv_p25"],
                "p50": benchmark["ltv_p50"],
                "p75": benchmark["ltv_p75"],
            }
        }

    async def improve_models_with_aggregated_data(self):
        """
        Use cross-company patterns to improve ML models.

        Example: Train churn model on aggregated behavioral patterns
        (not raw customer data).
        """
        async with self.insights_engine.connect() as conn:
            # Get aggregated behavioral features across companies
            result = await conn.execute("""
                SELECT
                    segment_id,
                    AVG(avg_churn_risk) as typical_churn,
                    AVG(avg_ltv) as typical_ltv,
                    COUNT(*) as observations
                FROM company_snapshots
                CROSS JOIN LATERAL jsonb_each(segment_distribution) as seg(segment_id, stats)
                GROUP BY segment_id
                HAVING COUNT(*) >= 3  -- Need at least 3 companies
            """)

            patterns = result.fetchall()

        # Use patterns to refine model (not training on individual customers)
        # E.g., "deal_hunter + premium segment typically has 18% churn"
        # This becomes a prior/baseline for the model

        return patterns
```

### Insights API Endpoints

```python
# platform/api/routers/insights.py

from fastapi import APIRouter, Depends
from platform.services.insights_aggregator import InsightsAggregator
from shared.auth.dependencies import require_api_key

router = APIRouter(
    prefix="/api/insights",
    tags=["insights"],
    dependencies=[Depends(require_api_key)]
)

@router.get("/benchmarks/{industry}")
async def get_industry_benchmarks(industry: str):
    """
    Get anonymized industry benchmarks.

    Example: "How does my churn compare to other retail companies?"

    Returns aggregated data across multiple companies - no individual
    company data exposed.
    """
    aggregator = InsightsAggregator(os.getenv("INSIGHTS_DB_URL"))
    return await aggregator.get_industry_benchmarks(industry)


@router.get("/my-position")
async def compare_to_benchmarks(tenant_id: str = Depends(get_current_tenant_id)):
    """
    Compare current tenant's metrics to industry benchmarks.

    Shows: "Your churn is 22%, industry average is 26.5%"
    """
    aggregator = InsightsAggregator(os.getenv("INSIGHTS_DB_URL"))

    # Get benchmarks
    benchmarks = await aggregator.get_industry_benchmarks("retail")

    # Get tenant's current stats
    from shared.database.tenant_resolver import tenant_resolver
    tenant_engine = tenant_resolver.get_async_engine(tenant_id)

    async with tenant_engine.connect() as conn:
        result = await conn.execute("""
            SELECT
                AVG(churn_risk_score) as my_churn,
                AVG(lifetime_value) as my_ltv
            FROM platform.customer_profiles
        """)
        my_stats = result.fetchone()

    return {
        "my_metrics": {
            "churn": my_stats["my_churn"],
            "ltv": my_stats["my_ltv"]
        },
        "industry_benchmarks": benchmarks,
        "comparison": {
            "churn_vs_industry": (
                "better" if my_stats["my_churn"] < benchmarks["avg_churn"]
                else "worse"
            ),
            "ltv_percentile": (
                "top_25%" if my_stats["my_ltv"] > benchmarks["ltv_percentiles"]["p75"]
                else "top_50%" if my_stats["my_ltv"] > benchmarks["ltv_percentiles"]["p50"]
                else "below_median"
            )
        }
    }
```

---

## New Company Onboarding

### Automated Provisioning

```python
# platform/admin/tenant_provisioning.py

async def provision_new_tenant(
    tenant_id: str,
    company_name: str,
    industry: str,
    database_tier: str = "starter"
):
    """
    Provision complete infrastructure for new company.

    Steps:
    1. Create database (or database within shared instance)
    2. Run schema migrations
    3. Create API keys
    4. Set up subdomain
    5. Seed initial data
    """

    # 1. Create database
    if database_tier == "dedicated":
        db_url = await create_dedicated_database(tenant_id)
    else:
        db_url = await create_database_in_shared_instance(tenant_id)

    # 2. Run migrations to create schemas
    await run_migrations(db_url)

    # 3. Register tenant
    await register_tenant(
        tenant_id=tenant_id,
        company_name=company_name,
        industry=industry,
        db_url=db_url
    )

    # 4. Generate API key
    api_key = await generate_tenant_api_key(tenant_id)

    # 5. Create subdomain (if using subdomain routing)
    subdomain = f"{tenant_id}.quimbi.ai"
    await configure_subdomain(subdomain, tenant_id)

    return {
        "tenant_id": tenant_id,
        "database_url": db_url,  # For their records only
        "api_key": api_key,
        "subdomain": subdomain,
        "status": "provisioned"
    }


async def run_migrations(db_url: str):
    """Run all schema migrations on new tenant database."""
    import subprocess

    # Create schemas
    subprocess.run([
        "psql", db_url, "-c",
        "CREATE SCHEMA platform; CREATE SCHEMA support_app; CREATE SCHEMA shared;"
    ])

    # Run Alembic migrations
    # (Point Alembic to tenant database temporarily)
    os.environ["DATABASE_URL"] = db_url
    subprocess.run(["alembic", "upgrade", "head"])
```

---

## Migration from Current Setup

### Current State

You currently have:
```
Single database: railway
  - All tables in public schema
  - Multi-tenant via tenant_id column
```

### Migration Strategy

**Phase 1: Keep Current, Add Database Routing Code**
```python
# Don't migrate data yet, just add the code infrastructure

# 1. Add tenant resolver (but only returns one DB for now)
class TenantDatabaseResolver:
    def get_db_url(self, tenant_id: str):
        # For now, everyone uses same database
        return os.getenv("DATABASE_URL")

# 2. Update code to use tenant-aware sessions
# 3. Test that it works with current setup
```

**Phase 2: Create Schema Separation in Current Database**
```sql
-- In your current database, create schemas
CREATE SCHEMA platform;
CREATE SCHEMA support_app;

-- Move tables
ALTER TABLE customer_profiles SET SCHEMA platform;
ALTER TABLE tickets SET SCHEMA support_app;
```

**Phase 3: First Customer Splits Off**
```python
# When you get a new customer OR when Linda wants dedicated DB:

# 1. Provision new database: linda_quilting
# 2. Export Linda's data from current database
pg_dump --data-only --table='*' \
  -n platform -n support_app \
  -t "*WHERE tenant_id='linda_quilting'" \
  railway > linda_export.sql

# 3. Import to new database
psql linda_quilting < linda_export.sql

# 4. Update tenant resolver
tenant_db_map["linda_quilting"] = "postgresql://...linda_quilting"

# 5. Test Linda's subdomain routes to new database
# 6. Remove Linda's data from old database
```

**Phase 4: Repeat for Each Customer**
- Gradually migrate customers to their own databases
- Eventually old shared database only has legacy/archived data

---

## Security & Access Control

### Principle: Complete Database Isolation

**Linda's team CANNOT access Outdoor Gear's database even if they wanted to:**

```python
# Their API key only resolves to their database
linda_api_key → tenant_id="linda_quilting" → linda_quilting_db

# Impossible to access other tenant data (no shared tables to leak)
```

**Database credentials are per-tenant:**
```env
# Environment variables
LINDA_DB_URL=postgresql://linda_user:linda_pass@host/linda_quilting
OUTDOOR_DB_URL=postgresql://outdoor_user:outdoor_pass@host/outdoor_gear

# linda_user has NO access to outdoor_gear database
# outdoor_user has NO access to linda_quilting database
```

### Insights Database Access

**Only platform infrastructure can access insights database:**

```python
# Insights aggregator runs as background job
# NOT exposed to tenant APIs
# Reads from all tenant databases (read-only)
# Writes aggregates to insights database

# Tenants can query benchmarks via API, but can't access raw insights DB
```

---

## Cost Analysis

### Scenario: 10 Companies

**Option 1: Dedicated PostgreSQL per Company**
```
10 companies × $15/month (Railway Postgres Starter) = $150/month
High-volume company: $50/month (Pro tier)
Total: ~$200/month
```

**Option 2: Shared Instance**
```
1 PostgreSQL Pro instance: $50/month
  - Holds 10 separate databases (linda_quilting, outdoor_gear, etc.)
Total: $50/month
```

**Recommended:**
- Start with Option 2 (shared instance)
- Move high-value customers to dedicated instances as needed
- Charge customers enough to cover their database costs

---

## Summary

### Your Multi-Tenant Model

✅ **Database per company** - complete isolation, no shared tables
✅ **Shared instance option** - cost-effective for small customers
✅ **Platform + app schemas** - within each company database
✅ **Insights aggregator** - separate database, anonymized cross-company intelligence
✅ **No data cross-pollination** - heavy abstraction, statistical aggregates only

### Implementation Priority

**Week 1-2:** Set up database-per-tenant infrastructure (routing, resolver)
**Week 3-4:** Implement insights aggregator with first anonymized patterns
**Month 2+:** Migrate existing companies to dedicated databases as needed

This gives you true multi-tenancy with complete data isolation while still allowing cross-company learning through carefully abstracted insights.
