# Quimbi Platform Architecture: Horizontal AI Brain + Modular Applications

**Date**: 2025-11-24
**Vision**: Quimbi as a reusable customer intelligence platform, not just a ticketing system

---

## The Problem You're Solving

**Current Risk:**
If you keep adding ticketing features (agents, SLA, assignments) directly into the Quimbi backend, you create:
- ❌ A "ticketing system with ML" instead of "ML platform with applications"
- ❌ Hard to reuse for marketing automation, sales CRM, analytics tools
- ❌ Ticketing logic mixed with AI/ML logic
- ❌ Difficult to sell as a platform to other use cases

**Your Vision:**
- ✅ **Quimbi = Horizontal customer intelligence platform** (the "brain")
- ✅ **Applications = Vertical solutions** that leverage the brain (support, marketing, sales, etc.)
- ✅ Clean separation, reusable AI, pluggable applications

---

## Proposed Architecture: "Platform + Apps"

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Support    │  │   Marketing  │  │    Sales     │         │
│  │     App      │  │      App     │  │     App      │  (more) │
│  │              │  │              │  │              │         │
│  │ • Tickets    │  │ • Campaigns  │  │ • Deals      │         │
│  │ • Agents     │  │ • Journeys   │  │ • Leads      │         │
│  │ • SLA        │  │ • Segments   │  │ • Outreach   │         │
│  │ • Assignments│  │ • A/B Tests  │  │ • Scoring    │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                  │
│         └─────────────────┴─────────────────┘                  │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            │ Unified API
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     QUIMBI PLATFORM                             │
│                   (Customer Intelligence Brain)                 │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              CORE INTELLIGENCE API                         ││
│  │                                                            ││
│  │  /api/intelligence/                                        ││
│  │    • analyze_customer(customer_id, context)                ││
│  │    • predict_churn(customer_id)                            ││
│  │    • forecast_ltv(customer_id, horizon)                    ││
│  │    • segment_customer(behavioral_data)                     ││
│  │    • score_customer(scoring_context)                       ││
│  │    • explain_behavior(customer_id, question)               ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              AI GENERATION API                             ││
│  │                                                            ││
│  │  /api/generation/                                          ││
│  │    • generate_message(context, channel, tone)              ││
│  │    • suggest_actions(context, goal)                        ││
│  │    • recommend_content(customer_profile, objective)        ││
│  │    • optimize_timing(customer_profile, message_type)       ││
│  │    • personalize_offer(customer_profile, products)         ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              DATA INGESTION API                            ││
│  │                                                            ││
│  │  /api/data/                                                ││
│  │    • ingest_orders(source, orders[])                       ││
│  │    • ingest_interactions(source, interactions[])           ││
│  │    • ingest_events(source, events[])                       ││
│  │    • sync_customer(source, customer_data)                  ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              ML CORE (Internal)                            ││
│  │                                                            ││
│  │    • Segmentation Engine (14 axes, K-Means clustering)     ││
│  │    • Churn Model (LightGBM binary classifier)              ││
│  │    • LTV Model (LightGBM Gamma regression)                 ││
│  │    • Feature Extraction (66 behavioral features)           ││
│  │    • Claude Integration (AI generation)                    ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              PLATFORM DATA LAYER                           ││
│  │                                                            ││
│  │    • Customer Profiles (basic identity + external refs)    ││
│  │    • Behavioral Analytics (segments, features, scores)     ││
│  │    • ML Model Storage (trained models, centroids)          ││
│  │    • Intelligence Cache (Redis - DNA, predictions)         ││
│  │                                                            ││
│  │  NOTE: Does NOT store operational data (tickets, agents,  ││
│  │        campaigns, deals - that lives in Applications)      ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Data Sources
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   ┌─────────┐         ┌─────────┐        ┌─────────┐
   │ Shopify │         │ Custom  │        │  Other  │
   │   API   │         │   DB    │        │ Sources │
   └─────────┘         └─────────┘        └─────────┘
```

---

## Key Design Principles

### 1. **Quimbi Platform = Stateless Intelligence Layer**

**What it DOES store:**
- Customer behavioral profiles (segments, DNA, features)
- ML model artifacts (trained models, centroids, coefficients)
- Analytics cache (computed predictions, scores)
- **Minimal identity data** (customer_id, external_refs, basic demographics)

**What it DOES NOT store:**
- ❌ Operational workflow data (tickets, agents, campaigns, deals)
- ❌ Application-specific state (SLA timers, assignment queues, campaign schedules)
- ❌ Rich customer contact info (Applications own this)
- ❌ Business logic for specific use cases

**Why:** Keep the platform lightweight, fast, and reusable across any application.

---

### 2. **Applications = Stateful Operational Systems**

Each application is a **separate codebase** (or module) that:
- Owns its operational data
- Calls Quimbi for intelligence
- Implements domain-specific workflows
- Has its own database, auth, UI

**Example: Support App**
```
support-app/
├── models/
│   ├── ticket.py          ← Owns ticket data
│   ├── agent.py           ← Owns agent data
│   ├── assignment.py      ← Owns routing logic
│   └── sla.py             ← Owns SLA tracking
├── services/
│   ├── quimbi_client.py   ← Calls Quimbi Platform API
│   ├── ticket_service.py
│   ├── assignment_service.py
│   └── sla_service.py
├── api/
│   └── routers/
│       ├── tickets.py
│       ├── agents.py
│       └── ai.py          ← Proxies to Quimbi
└── database/              ← Separate DB for support app
```

**Example: Marketing App** (future)
```
marketing-app/
├── models/
│   ├── campaign.py        ← Owns campaign data
│   ├── journey.py         ← Owns journey data
│   ├── ab_test.py         ← Owns experiment data
│   └── segment.py         ← Owns segment definitions
├── services/
│   ├── quimbi_client.py   ← Calls same Quimbi API
│   ├── campaign_service.py
│   └── targeting_service.py
├── api/
└── database/              ← Separate DB for marketing app
```

---

### 3. **Shared Intelligence, Separate Operational Data**

```
┌─────────────────────────────────────────────────────────┐
│  QUIMBI PLATFORM                                        │
│                                                         │
│  Customer "12345":                                      │
│    • Archetype: "Premium Deal-Hunter Long-Term"        │
│    • Churn Risk: 0.28 (low)                            │
│    • LTV 12mo: $450                                    │
│    • Segments: {price_sensitivity: "deal_hunter", ...} │
│    • External Refs: {shopify: "abc", hubspot: "xyz"}   │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │ Same intelligence, different contexts
                         │
      ┌──────────────────┴───────────────────┐
      │                                      │
      ▼                                      ▼
┌─────────────────┐                  ┌─────────────────┐
│  SUPPORT APP    │                  │  MARKETING APP  │
│                 │                  │                 │
│  Customer 12345:│                  │  Customer 12345:│
│  • 3 open       │                  │  • In campaign  │
│    tickets      │                  │    "Black Friday│
│  • Assigned to  │                  │  • Email opened │
│    Agent Sarah  │                  │    3 times      │
│  • SLA: 2h left │                  │  • Segment: VIP │
│  • Last contact:│                  │  • Next send:   │
│    2 days ago   │                  │    tomorrow 9am │
└─────────────────┘                  └─────────────────┘
```

**Benefits:**
- ✅ Applications don't duplicate ML/AI logic
- ✅ Consistent customer intelligence across all apps
- ✅ Quimbi can be improved once, benefits all apps
- ✅ Each app owns its domain without interfering with others

---

## Migration Path from Current State

### Current State Analysis

Your `unified-segmentation-ecommerce` repo currently has:

**Platform-worthy (keep in Quimbi):**
```
✅ backend/ml/                    ← Churn/LTV models
✅ backend/segmentation/          ← 14-axis segmentation
✅ backend/services/ai_service.py ← AI generation
✅ backend/models/customer_profiles table
✅ backend/models/archetype_definitions table
✅ backend/cache/redis_cache.py   ← Intelligence caching
```

**Application-specific (extract to Support App):**
```
❌ backend/models/ticket.py       ← Support domain
❌ backend/api/routers/tickets.py ← Support routes
❌ backend/services/scoring_service.py (uses ML but is support-specific)
❌ Future: agents, assignments, SLA ← All support domain
```

**Shared/Unclear:**
```
⚠️ backend/api/routers/customers.py  ← Needs split
⚠️ backend/integrations/             ← Could be shared or app-specific
⚠️ backend/main.py                   ← Needs reorganization
```

---

### Recommended Migration: "Modular Monolith with Clear Boundaries"

Instead of physically splitting codebases now, **organize the existing repo** to support the platform vision:

```
unified-segmentation-ecommerce/
│
├── platform/                    ← QUIMBI PLATFORM CODE
│   ├── api/
│   │   └── routers/
│   │       ├── intelligence.py  ← Customer analysis, predictions
│   │       ├── generation.py    ← AI generation endpoints
│   │       └── data.py          ← Data ingestion
│   ├── ml/
│   │   ├── churn_model.py
│   │   ├── ltv_model.py
│   │   └── training/
│   ├── segmentation/
│   │   ├── feature_extraction.py
│   │   ├── clustering.py
│   │   └── archetype_naming.py
│   ├── services/
│   │   ├── intelligence_service.py
│   │   └── ai_generation_service.py
│   ├── models/
│   │   ├── customer_profile.py
│   │   └── archetype.py
│   └── cache/
│       └── intelligence_cache.py
│
├── apps/                        ← APPLICATIONS
│   │
│   └── support/                 ← SUPPORT APPLICATION
│       ├── api/
│       │   └── routers/
│       │       ├── tickets.py
│       │       ├── agents.py
│       │       ├── assignments.py
│       │       └── sla.py
│       ├── models/
│       │   ├── ticket.py
│       │   ├── agent.py
│       │   ├── assignment.py
│       │   └── sla.py
│       ├── services/
│       │   ├── platform_client.py  ← Calls platform/api
│       │   ├── ticket_service.py
│       │   ├── assignment_service.py
│       │   └── sla_service.py
│       └── integrations/
│           ├── gorgias/
│           ├── shopify/
│           └── slack/
│
├── shared/                      ← SHARED UTILITIES
│   ├── auth/
│   ├── database/
│   ├── middleware/
│   └── config/
│
├── main.py                      ← Application entry point
└── platform_main.py             ← Platform API entry point (optional)
```

---

## API Design: Platform vs Application

### Platform API (Quimbi Intelligence)

**Namespace:** `/api/intelligence/*`

```python
# Generic customer intelligence - no domain assumptions

POST /api/intelligence/analyze
{
  "customer_id": "12345",
  "context": {
    "interaction_history": [...],
    "orders": [...],
    "events": [...]
  }
}
→ Returns: DNA profile, segments, archetype, behavioral scores

POST /api/intelligence/predict/churn
{
  "customer_id": "12345"
}
→ Returns: Churn probability, risk factors, retention recommendations

POST /api/intelligence/predict/ltv
{
  "customer_id": "12345",
  "horizon_months": 12
}
→ Returns: Forecasted LTV, confidence interval

POST /api/intelligence/generate/message
{
  "customer_profile": {...},
  "context": {
    "conversation": [...],
    "goal": "resolve_support_issue",  # or "nurture_lead", "upsell"
    "channel": "email",
    "constraints": {"tone": "empathetic", "length": "medium"}
  }
}
→ Returns: Generated message, personalization notes

POST /api/intelligence/recommend/actions
{
  "customer_profile": {...},
  "scenario": "support_ticket",  # or "sales_opportunity", "marketing_campaign"
  "context": {...}
}
→ Returns: Recommended actions, priorities, reasoning
```

**Key Characteristics:**
- ✅ Generic, reusable across any application
- ✅ Takes data in, returns intelligence
- ✅ No domain-specific assumptions (tickets, campaigns, etc.)
- ✅ Stateless - doesn't care where data came from

---

### Application API (Support App Example)

**Namespace:** `/api/support/*`

```python
# Support-specific operations

GET /api/support/tickets
→ Returns: Ticket list (enriched with Quimbi intelligence)

POST /api/support/tickets
{
  "customer_id": "12345",
  "subject": "Help with order",
  "channel": "email"
}
→ Creates ticket, calls Quimbi for initial scoring

GET /api/support/tickets/{id}
→ Returns: Ticket details + customer DNA from Quimbi

POST /api/support/tickets/{id}/ai-draft
→ Calls Quimbi /api/intelligence/generate/message

POST /api/support/agents/{id}/assign-next
→ Uses Quimbi customer scores + support-specific routing logic
```

**Key Characteristics:**
- ✅ Domain-specific (support workflow)
- ✅ Orchestrates support operations
- ✅ Calls Quimbi for intelligence
- ✅ Owns support data (tickets, agents, SLA)

---

## Deployment Options

### Option 1: Monorepo, Shared Deployment (Easiest - Start Here)

```
Railway Service: "quimbi-unified"
  - Deploys entire codebase
  - Exposes both /api/intelligence/* and /api/support/*
  - Shares database, Redis, resources
  - Single deployment pipeline
```

**Pros:**
- ✅ Zero network latency between platform and app
- ✅ Simple deployment and debugging
- ✅ Shared resources (DB connections, Redis, cache)
- ✅ Easy to refactor and iterate

**Cons:**
- ⚠️ Platform and app coupled in deployment
- ⚠️ Can't scale independently (yet)

**When to use:** MVP, early development, proving the concept

---

### Option 2: Monorepo, Separate Deployments (Later)

```
Railway Service 1: "quimbi-platform"
  - Deploys platform/ directory
  - Exposes /api/intelligence/*
  - Optimized for ML inference (CPU/memory)

Railway Service 2: "quimbi-support"
  - Deploys apps/support/ directory
  - Exposes /api/support/*
  - Calls quimbi-platform API
  - Optimized for web traffic
```

**Pros:**
- ✅ Independent scaling
- ✅ Independent deployment schedules
- ✅ Clear separation in production
- ✅ Still share codebase for development

**Cons:**
- ⚠️ Network latency between services
- ⚠️ Need service-to-service auth
- ⚠️ More complex debugging

**When to use:** After validating platform model, when scale demands it

---

### Option 3: Separate Repos (Future)

```
Repo 1: quimbi-platform
Repo 2: quimbi-support-app
Repo 3: quimbi-marketing-app
```

**Pros:**
- ✅ Complete independence
- ✅ Different teams, languages, deployment
- ✅ True platform model

**Cons:**
- ⚠️ Maximum complexity
- ⚠️ Code sharing requires packages
- ⚠️ Integration testing harder

**When to use:** When you have multiple mature applications and separate teams

---

## Example: How Support App Uses Platform

### Scenario: Agent Opens Ticket

**Support App Code:**
```python
# apps/support/api/routers/tickets.py

@router.get("/api/support/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    # 1. Fetch ticket from support database
    ticket = await support_db.get_ticket(ticket_id)

    # 2. Call Quimbi Platform for customer intelligence
    customer_intel = await platform_client.analyze_customer(
        customer_id=ticket.customer_id,
        context={
            "recent_orders": await shopify.get_orders(ticket.customer_id),
            "interaction_history": await support_db.get_customer_tickets(ticket.customer_id)
        }
    )

    # 3. Enrich ticket response with intelligence
    return {
        "ticket": ticket.dict(),
        "customer": {
            "dna": customer_intel["archetype"],
            "churn_risk": customer_intel["churn_prediction"],
            "ltv_12mo": customer_intel["ltv_forecast"],
            "communication_style": customer_intel["recommendations"]["communication"]
        },
        "ai_suggestions": {
            "draft": await platform_client.generate_message(
                customer_profile=customer_intel,
                context={"conversation": ticket.messages, "goal": "resolve_support_issue"}
            ),
            "actions": await platform_client.recommend_actions(
                customer_profile=customer_intel,
                scenario="support_ticket",
                context=ticket.dict()
            )
        }
    }
```

**Platform Client:**
```python
# apps/support/services/platform_client.py

class QuimbiPlatformClient:
    """Client for calling Quimbi Platform APIs"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.cache = redis.Redis()

    async def analyze_customer(self, customer_id: str, context: dict):
        # Check cache first
        cache_key = f"customer_intel:{customer_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return json.loads(cached)

        # Call platform API
        response = await httpx.post(
            f"{self.base_url}/api/intelligence/analyze",
            json={"customer_id": customer_id, "context": context},
            headers={"X-API-Key": self.api_key}
        )

        result = response.json()

        # Cache for 15 minutes
        await self.cache.setex(cache_key, 900, json.dumps(result))

        return result
```

---

## Benefits of This Architecture

### ✅ For Platform Development

1. **Reusability**
   - Write ML models once, use in support, marketing, sales
   - Segmentation benefits all applications
   - AI generation adapts to any context

2. **Focus**
   - Platform team focuses on ML accuracy, intelligence quality
   - Not distracted by support workflows, SLA logic, etc.

3. **Innovation Speed**
   - Improve churn model → all apps benefit immediately
   - Add new behavioral axis → all apps get richer profiles
   - New AI capability → available to all apps

### ✅ For Application Development

1. **Domain Clarity**
   - Support app owns support logic (SLA, routing, agents)
   - Marketing app owns campaign logic (journeys, segments)
   - No confusion about responsibilities

2. **Freedom**
   - Build UI/UX specific to use case
   - Optimize workflows for domain
   - Choose best tools for job

3. **Intelligence Layer**
   - Don't rebuild ML capabilities
   - Consistent customer understanding
   - AI generation handles complexity

### ✅ For Business

1. **Platform Play**
   - Sell Quimbi Platform API to other companies
   - Build multiple applications on same intelligence
   - Leverage AI investment across products

2. **Flexibility**
   - Add new applications without modifying platform
   - Experiment with use cases
   - Partner integrations easier

---

## Migration Roadmap

### Week 1-2: Reorganize Current Codebase
- [ ] Create `platform/` and `apps/support/` directories
- [ ] Move ML code to `platform/`
- [ ] Move ticket code to `apps/support/`
- [ ] Create platform API namespace `/api/intelligence/*`
- [ ] Create support API namespace `/api/support/*`
- [ ] Still deploy as single service (Option 1)

### Week 3-4: Add Missing Support Features
- [ ] Add Agent model to `apps/support/models/`
- [ ] Add Assignment service
- [ ] Add SLA tracking
- [ ] Keep using platform intelligence via internal calls

### Week 5-8: Build Marketing App (Validate Platform Model)
- [ ] Create `apps/marketing/` directory
- [ ] Build campaign models
- [ ] Reuse Quimbi intelligence APIs
- [ ] Prove platform can support multiple apps

### Week 9-12: Optimize Platform
- [ ] Improve intelligence API performance
- [ ] Better caching strategies
- [ ] Add new ML capabilities
- [ ] Document platform API for external use

### Later: Consider Physical Split (Option 2/3)
- [ ] Only if scaling demands it
- [ ] Only if team structure requires it
- [ ] Only if platform has external customers

---

## Conclusion

**You get both:**

1. ✅ **Quimbi as a true "AI brain"**
   - Horizontal platform for customer intelligence
   - Reusable across support, marketing, sales, analytics
   - Not locked into one domain

2. ✅ **Modular applications**
   - Each owns its domain (support, marketing, etc.)
   - Leverage platform intelligence
   - Can be built, deployed, scaled independently

3. ✅ **No premature splitting**
   - Start as organized monolith (fast, low latency)
   - Clear boundaries for future split
   - Migrate to separate services when needed, not before

**Next step:** Reorganize your current codebase into `platform/` and `apps/support/` to establish clear boundaries, then build missing support features while keeping the platform generic and reusable.
