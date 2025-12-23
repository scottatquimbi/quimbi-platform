# Data Architecture: CRUD and Database Strategy for Platform + Apps

**Date**: 2025-11-24
**Focus**: Where data lives, who owns CRUD, database separation strategy

---

## The Core Question

**"Should Platform and Apps share a database or have separate databases?"**

This is the critical decision that affects everything else.

---

## Option 1: Shared Database with Schema Separation (RECOMMENDED START)

### Structure

```
PostgreSQL Database: "quimbi"
│
├── Schema: platform
│   ├── customer_profiles          ← Platform owns
│   ├── archetype_definitions      ← Platform owns
│   ├── dim_archetype_l1/l2/l3     ← Platform owns
│   ├── ml_model_metadata          ← Platform owns
│   └── behavioral_analytics       ← Platform owns
│
├── Schema: support_app
│   ├── tickets                    ← Support app owns
│   ├── ticket_messages            ← Support app owns
│   ├── ticket_notes               ← Support app owns
│   ├── ticket_ai_recommendations  ← Support app owns
│   ├── agents                     ← Support app owns
│   ├── assignments                ← Support app owns
│   ├── sla_policies               ← Support app owns
│   └── sla_tracking               ← Support app owns
│
├── Schema: marketing_app (future)
│   ├── campaigns
│   ├── journeys
│   ├── segments
│   └── ab_tests
│
└── Schema: shared
    ├── tenants                    ← Multi-tenancy
    └── api_keys                   ← Authentication
```

### CRUD Ownership Rules

**Platform CRUD:**
```python
# platform/api/routers/intelligence.py

# Platform can READ/WRITE its own tables
@router.post("/api/intelligence/customer/sync")
async def sync_customer_profile(customer_data: dict):
    """Platform maintains customer behavioral profiles"""
    async with get_db() as db:
        # Platform writes to platform.customer_profiles
        await db.execute(
            "INSERT INTO platform.customer_profiles (...) VALUES (...)"
        )
```

**Support App CRUD:**
```python
# apps/support/api/routers/tickets.py

# Support app can READ/WRITE its own tables
@router.post("/api/support/tickets")
async def create_ticket(ticket: TicketCreate):
    async with get_db() as db:
        # Support writes to support_app.tickets
        ticket = await db.execute(
            "INSERT INTO support_app.tickets (...) VALUES (...)"
        )

        # Support can READ platform tables (but not write)
        customer_profile = await db.execute(
            "SELECT * FROM platform.customer_profiles WHERE customer_id = :id"
        )

        return enrich_with_platform_data(ticket, customer_profile)
```

### Access Control Matrix

| Schema | Platform | Support App | Marketing App |
|--------|----------|-------------|---------------|
| **platform.*** | READ/WRITE | READ only | READ only |
| **support_app.*** | READ only (for analytics) | READ/WRITE | No access |
| **marketing_app.*** | READ only (for analytics) | No access | READ/WRITE |
| **shared.*** | READ/WRITE | READ/WRITE | READ/WRITE |

### Database Permissions (PostgreSQL Roles)

```sql
-- Platform role
CREATE ROLE quimbi_platform;
GRANT ALL ON SCHEMA platform TO quimbi_platform;
GRANT SELECT ON SCHEMA support_app TO quimbi_platform;  -- Read for analytics
GRANT ALL ON SCHEMA shared TO quimbi_platform;

-- Support app role
CREATE ROLE quimbi_support_app;
GRANT ALL ON SCHEMA support_app TO quimbi_support_app;
GRANT SELECT ON SCHEMA platform TO quimbi_support_app;  -- Read for enrichment
GRANT ALL ON SCHEMA shared TO quimbi_support_app;

-- Marketing app role
CREATE ROLE quimbi_marketing_app;
GRANT ALL ON SCHEMA marketing_app TO quimbi_marketing_app;
GRANT SELECT ON SCHEMA platform TO quimbi_marketing_app;
GRANT ALL ON SCHEMA shared TO quimbi_marketing_app;
```

### Migration Strategy

**Currently you have:**
```
public.customer_profiles      ← Platform data
public.tickets                ← Support app data
public.archetype_definitions  ← Platform data
```

**Migration steps:**
```sql
-- 1. Create schemas
CREATE SCHEMA platform;
CREATE SCHEMA support_app;
CREATE SCHEMA shared;

-- 2. Move platform tables
ALTER TABLE public.customer_profiles SET SCHEMA platform;
ALTER TABLE public.archetype_definitions SET SCHEMA platform;
ALTER TABLE public.dim_archetype_l1 SET SCHEMA platform;
ALTER TABLE public.dim_archetype_l2 SET SCHEMA platform;
ALTER TABLE public.dim_archetype_l3 SET SCHEMA platform;

-- 3. Move support app tables
ALTER TABLE public.tickets SET SCHEMA support_app;
ALTER TABLE public.ticket_messages SET SCHEMA support_app;
ALTER TABLE public.ticket_notes SET SCHEMA support_app;
ALTER TABLE public.ticket_ai_recommendations SET SCHEMA support_app;

-- 4. Move shared tables
ALTER TABLE public.tenants SET SCHEMA shared;

-- 5. Update foreign keys to use schema-qualified names
```

### Code Changes

**Platform models:**
```python
# platform/models/customer_profile.py

class CustomerProfile(Base):
    __tablename__ = "customer_profiles"
    __table_args__ = {"schema": "platform"}  # ← Schema specified

    customer_id = Column(String, primary_key=True)
    archetype_id = Column(String)
    # ... rest of model
```

**Support app models:**
```python
# apps/support/models/ticket.py

class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"schema": "support_app"}  # ← Schema specified

    id = Column(UUID, primary_key=True)
    customer_id = Column(String)  # ← Reference to platform.customer_profiles
    # ... rest of model
```

### Pros/Cons

**Pros:**
- ✅ Single database connection pool
- ✅ True ACID transactions across schemas (if needed)
- ✅ Simple deployment (one database to manage)
- ✅ Easy JOINs for analytics/reporting
- ✅ Cheaper (one database instance)
- ✅ Clear ownership via schemas
- ✅ Database-level access control

**Cons:**
- ⚠️ Apps still coupled at database level
- ⚠️ Can't scale databases independently
- ⚠️ Schema migrations need coordination
- ⚠️ One database failure affects everything

**When to use:** MVP, early stage, proving the model, same team managing everything

---

## Option 2: Separate Databases (FUTURE)

### Structure

```
Database 1: "quimbi_platform"
├── customer_profiles
├── archetype_definitions
├── dim_archetype_l1/l2/l3
└── ml_model_metadata

Database 2: "quimbi_support"
├── tickets
├── ticket_messages
├── agents
├── assignments
└── sla_tracking

Database 3: "quimbi_marketing" (future)
├── campaigns
├── journeys
└── segments

Database 4: "quimbi_shared" (optional)
├── tenants
└── api_keys
```

### CRUD Ownership Rules

**Platform CRUD:**
```python
# platform/api/routers/intelligence.py

# Platform ONLY accesses platform database
async def analyze_customer(customer_id: str, context: dict):
    async with get_platform_db() as db:  # ← Platform DB connection
        # Write to platform database
        profile = await db.execute(
            "INSERT INTO customer_profiles (...) VALUES (...)"
        )
        return profile
```

**Support App CRUD:**
```python
# apps/support/api/routers/tickets.py

# Support app ONLY accesses support database
async def create_ticket(ticket_data: dict):
    async with get_support_db() as db:  # ← Support DB connection
        # Write to support database
        ticket = await db.execute(
            "INSERT INTO tickets (...) VALUES (...)"
        )

    # To get customer intelligence, call Platform API (not direct DB access)
    customer_intel = await platform_client.analyze_customer(
        customer_id=ticket.customer_id,
        context={...}
    )

    return enrich_ticket(ticket, customer_intel)
```

### Data Synchronization

**Challenge:** Apps need customer data for operations, Platform needs behavioral data from apps.

**Solution: Event-Driven Sync**

```python
# apps/support/services/ticket_service.py

async def create_ticket(ticket_data: dict):
    # 1. Create ticket in support database
    ticket = await support_db.create_ticket(ticket_data)

    # 2. Publish event for Platform to consume
    await event_bus.publish("customer.interaction.created", {
        "customer_id": ticket.customer_id,
        "interaction_type": "support_ticket",
        "channel": ticket.channel,
        "timestamp": ticket.created_at,
        "metadata": {
            "ticket_id": ticket.id,
            "subject": ticket.subject,
            "priority": ticket.priority
        }
    })

    return ticket
```

```python
# platform/events/handlers.py

@event_bus.subscribe("customer.interaction.created")
async def handle_customer_interaction(event: dict):
    """Platform consumes interaction events to update behavioral profiles"""
    async with get_platform_db() as db:
        # Update customer profile with new interaction
        await db.execute("""
            UPDATE customer_profiles
            SET last_interaction_at = :timestamp,
                interaction_count = interaction_count + 1
            WHERE customer_id = :customer_id
        """, event)

        # Invalidate cache
        await cache.delete(f"customer_intel:{event['customer_id']}")
```

**Event Bus Options:**
- **Simple:** Redis Pub/Sub
- **Robust:** RabbitMQ, AWS SQS, Google Pub/Sub
- **Streaming:** Apache Kafka (if high volume)

### Reference Data Sharing

**Problem:** Support app needs to know which customer_id to use, but customer data is in Platform DB.

**Solution 1: Platform provides customer lookup API**
```python
# apps/support/services/customer_service.py

async def find_or_create_customer(email: str):
    # Call Platform API to get/create customer
    customer = await platform_client.find_customer_by_email(email)

    if not customer:
        customer = await platform_client.create_customer({
            "email": email,
            "source": "support_app"
        })

    # Store customer_id reference in support database
    await support_db.execute(
        "INSERT INTO customer_references (customer_id, email) VALUES (:id, :email)",
        {"id": customer["customer_id"], "email": email}
    )

    return customer["customer_id"]
```

**Solution 2: Denormalize essential customer identity**
```python
# apps/support/models/customer_reference.py

class CustomerReference(Base):
    """Minimal customer identity cached in support app"""
    __tablename__ = "customer_references"

    customer_id = Column(String, primary_key=True)  # From Platform
    email = Column(String, unique=True, index=True)
    name = Column(String)
    last_synced = Column(DateTime)

    # NOTE: This is a cache, not source of truth
    # Platform owns full customer profile
```

### Pros/Cons

**Pros:**
- ✅ True independence - apps can scale databases separately
- ✅ Different database technologies if needed (Postgres for Platform, MySQL for Support, etc.)
- ✅ Database failures isolated
- ✅ Different backup/retention policies
- ✅ Clear API boundaries enforced

**Cons:**
- ⚠️ No cross-database JOINs (need to aggregate in application)
- ⚠️ No distributed transactions (eventual consistency)
- ⚠️ Event-driven complexity (message queues, sync issues)
- ⚠️ More infrastructure to manage
- ⚠️ Data duplication and sync problems

**When to use:** High scale, different teams, regulatory isolation, proven platform model

---

## Option 3: Hybrid Approach (PRAGMATIC)

### Structure

**Start with shared database (Option 1), but design APIs to hide it:**

```python
# apps/support/services/platform_client.py

class PlatformClient:
    """
    Abstract interface to Platform - currently direct DB access,
    future can be HTTP API without changing calling code
    """

    async def analyze_customer(self, customer_id: str, context: dict):
        # Current implementation: Direct DB access
        async with get_db() as db:
            return await db.execute(
                "SELECT * FROM platform.customer_profiles WHERE customer_id = :id"
            )

        # Future implementation: HTTP API call
        # return await httpx.post(f"{PLATFORM_URL}/api/intelligence/analyze", ...)
```

**Benefits:**
- ✅ Start simple (shared DB)
- ✅ Code ready for future split
- ✅ Can migrate incrementally
- ✅ No premature optimization

---

## Recommended Strategy

### Phase 1: Shared Database with Schemas (Months 1-6)

**Do this now:**

1. **Migrate to schema separation**
   ```sql
   CREATE SCHEMA platform;
   CREATE SCHEMA support_app;
   ALTER TABLE customer_profiles SET SCHEMA platform;
   ALTER TABLE tickets SET SCHEMA support_app;
   ```

2. **Establish CRUD boundaries**
   ```python
   # Platform models use schema="platform"
   # Support models use schema="support_app"
   # Enforce via code review
   ```

3. **Create abstraction layer**
   ```python
   # apps/support/services/platform_client.py
   # Hides whether Platform is same DB or API
   ```

4. **Single deployment**
   - One Railway service
   - One database
   - Fast iteration

**Success criteria:**
- ✅ Clear schema ownership
- ✅ No cross-schema writes (except via API/service layer)
- ✅ Code ready for future API split

---

### Phase 2: API Abstraction (Months 6-12)

**When:** After building 2+ apps (Support + Marketing)

**Do this:**

1. **Create Platform API endpoints**
   ```python
   # platform/api/routers/intelligence.py
   # Expose all platform functionality via REST
   ```

2. **Migrate apps to use APIs**
   ```python
   # apps/support/services/platform_client.py
   # Switch from DB queries to HTTP calls
   # Can do gradually, endpoint by endpoint
   ```

3. **Still same database and deployment**
   - Internal HTTP calls (fast)
   - But code ready for physical split

**Success criteria:**
- ✅ All cross-schema access via APIs
- ✅ No direct DB queries from apps to platform schema
- ✅ Can monitor API call patterns

---

### Phase 3: Physical Database Split (Year 2+)

**When:** Only if you hit real scaling limits or need true isolation

**Do this:**

1. **Create separate databases**
   ```sql
   CREATE DATABASE quimbi_platform;
   CREATE DATABASE quimbi_support;
   ```

2. **Data migration**
   ```bash
   # Export platform schema from shared DB
   pg_dump --schema=platform quimbi > platform.sql
   # Import to new database
   psql quimbi_platform < platform.sql
   ```

3. **Update connection strings**
   ```python
   # Platform uses PLATFORM_DATABASE_URL
   # Support uses SUPPORT_DATABASE_URL
   ```

4. **Deploy as separate services** (optional)
   ```yaml
   # Railway: quimbi-platform service
   # Railway: quimbi-support service
   ```

**Success criteria:**
- ✅ Databases scale independently
- ✅ No shared database locks
- ✅ Apps truly independent

---

## CRUD Patterns by Layer

### Platform Layer CRUD

**Platform owns:**
- Customer behavioral profiles (segments, DNA)
- ML model artifacts
- Archetype definitions
- Analytics aggregations

**Platform provides:**
```python
# platform/api/routers/intelligence.py

# Read customer intelligence
@router.get("/api/intelligence/customer/{customer_id}")
async def get_customer_intelligence(customer_id: str):
    async with get_platform_db() as db:
        profile = await db.query(CustomerProfile).filter_by(customer_id=customer_id).first()
        return profile.to_dict()

# Update customer profile (from data ingestion)
@router.post("/api/intelligence/customer/sync")
async def sync_customer_profile(data: CustomerDataSync):
    async with get_platform_db() as db:
        profile = CustomerProfile(
            customer_id=data.customer_id,
            archetype_id=calculate_archetype(data),
            # ... computed fields
        )
        db.add(profile)
        await db.commit()
    return {"status": "synced"}
```

**Platform does NOT:**
- ❌ Create/update tickets
- ❌ Manage agents or assignments
- ❌ Track SLA timers
- ❌ Store campaign schedules

---

### Application Layer CRUD

**Support app owns:**
- Tickets, messages, notes
- Agents, teams, roles
- Assignments, routing rules
- SLA policies and tracking

**Support app provides:**
```python
# apps/support/api/routers/tickets.py

# Create ticket
@router.post("/api/support/tickets")
async def create_ticket(ticket: TicketCreate):
    async with get_support_db() as db:
        # Write to support database
        new_ticket = Ticket(
            customer_id=ticket.customer_id,
            subject=ticket.subject,
            # ... operational fields
        )
        db.add(new_ticket)
        await db.commit()

    # Enrich with Platform intelligence
    customer_intel = await platform_client.get_customer_intelligence(ticket.customer_id)

    return {
        "ticket": new_ticket.dict(),
        "customer_dna": customer_intel["archetype"],
        "ai_draft": await platform_client.generate_message(...)
    }

# Update ticket
@router.patch("/api/support/tickets/{id}")
async def update_ticket(id: str, update: TicketUpdate):
    async with get_support_db() as db:
        ticket = await db.query(Ticket).filter_by(id=id).first()
        ticket.status = update.status
        await db.commit()
    return ticket
```

**Support app does NOT:**
- ❌ Modify customer_profiles directly
- ❌ Update archetype_definitions
- ❌ Retrain ML models
- ❌ Change segmentation logic

---

## Data Flow Examples

### Example 1: Create Ticket with AI Draft

**Shared Database Approach (Phase 1):**
```python
@router.post("/api/support/tickets")
async def create_ticket(ticket_data: dict):
    async with get_db() as db:
        # 1. Write to support_app.tickets
        ticket = Ticket(**ticket_data)
        db.add(ticket)

        # 2. Read from platform.customer_profiles (same transaction!)
        customer = await db.query(CustomerProfile).filter_by(
            customer_id=ticket.customer_id
        ).first()

        await db.commit()

    # 3. Generate AI draft using platform service
    from platform.services.ai_service import generate_draft_response
    draft = generate_draft_response({
        "ticket": ticket,
        "customer_profile": customer
    })

    return {"ticket": ticket.dict(), "ai_draft": draft}
```

**Separate Database Approach (Phase 3):**
```python
@router.post("/api/support/tickets")
async def create_ticket(ticket_data: dict):
    # 1. Write to support database
    async with get_support_db() as db:
        ticket = Ticket(**ticket_data)
        db.add(ticket)
        await db.commit()

    # 2. Call Platform API for customer intelligence
    customer_intel = await platform_client.get_customer_intelligence(
        ticket.customer_id
    )

    # 3. Call Platform API for AI draft
    draft = await platform_client.generate_message(
        customer_profile=customer_intel,
        context={"ticket": ticket.dict()}
    )

    return {"ticket": ticket.dict(), "ai_draft": draft}
```

---

## Migration Checklist

### ✅ Phase 1: Schema Separation (Week 1-2)

- [ ] Create `platform`, `support_app`, `shared` schemas
- [ ] Migrate existing tables to correct schemas
- [ ] Update SQLAlchemy models with `__table_args__ = {"schema": "..."}`
- [ ] Create database roles with appropriate permissions
- [ ] Update all queries to use schema-qualified table names
- [ ] Test that apps can't write to wrong schemas

### ✅ Phase 2: API Abstraction (Month 6+)

- [ ] Create Platform API endpoints for all intelligence operations
- [ ] Create `PlatformClient` service in support app
- [ ] Migrate support app to call APIs instead of direct DB queries
- [ ] Add caching to API calls
- [ ] Monitor API performance
- [ ] Ensure no direct cross-schema queries remain

### ✅ Phase 3: Physical Split (Year 2+)

- [ ] Provision separate databases
- [ ] Export/import data to new databases
- [ ] Update connection strings
- [ ] Implement event-driven sync if needed
- [ ] Deploy as separate services (optional)
- [ ] Monitor cross-service performance

---

## Recommended Starting Point

**Start with Option 1 (Shared Database with Schemas):**

```sql
-- Run this migration NOW
CREATE SCHEMA platform;
CREATE SCHEMA support_app;
CREATE SCHEMA shared;

-- Move tables (example)
ALTER TABLE customer_profiles SET SCHEMA platform;
ALTER TABLE tickets SET SCHEMA support_app;
ALTER TABLE tenants SET SCHEMA shared;
```

```python
# Update models
class CustomerProfile(Base):
    __tablename__ = "customer_profiles"
    __table_args__ = {"schema": "platform"}

class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"schema": "support_app"}
```

**Why:**
- ✅ Immediate clear ownership
- ✅ Zero performance impact
- ✅ Easy to implement (1-2 days)
- ✅ Foundation for future split
- ✅ Can still JOIN across schemas for analytics
- ✅ Database-enforced access control

**Then evolve naturally as your needs grow.**
