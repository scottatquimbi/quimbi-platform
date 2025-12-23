# Quimbi API Structure Analysis

**Date**: November 24, 2025
**Context**: Current API running at http://localhost:8000/docs
**Purpose**: Map current endpoints to platform architecture and identify what external teams should consume

---

## Current API Endpoints (Swagger UI)

### 1. **AI Endpoints** (Platform Intelligence - Core Brain)
These are the **platform intelligence APIs** that should be consumed by external apps:

```
GET  /api/ai/customers/{customer_id}/intelligence
     → Customer behavioral analysis, churn risk, LTV, segments
     → Platform API: Should become /api/intelligence/analyze

GET  /api/ai/tickets/{ticket_id}/recommendation
     → AI-powered ticket recommendations and actions
     → Platform API: Should become /api/generation/actions

GET  /api/ai/tickets/{ticket_id}/draft-response
     → AI-generated draft responses
     → Platform API: Should become /api/generation/message

POST /api/ai/tickets/{ticket_id}/regenerate-draft
     → Regenerate AI draft with new context
     → Platform API: Keep as /api/generation/message/regenerate
```

**Analysis**: These are **pure platform intelligence** endpoints. They consume ML/AI models and segmentation data from the `platform` schema. These should be the primary APIs external teams consume.

---

### 2. **Tickets Endpoints** (Support App - Operational)
These are **support application** operational endpoints (CRUD):

```
GET   /api/tickets
      → List tickets with smart ordering
      → Support App: Internal to Support frontend

POST  /api/tickets
      → Create new ticket
      → Support App: Could be exposed for external ticket creation

GET   /api/tickets/{ticket_id}
      → Get ticket details with full conversation
      → Support App: Internal to Support frontend

POST  /api/tickets/{ticket_id}/messages
      → Send message to ticket
      → Support App: Internal to Support frontend

GET   /api/tickets/{ticket_id}/score-breakdown
      → Get ticket scoring details
      → Support App: Internal debugging/transparency
```

**Analysis**: These are **operational CRUD** for the Support App. Most should remain internal to the support frontend. Exception: `POST /api/tickets` could be exposed for external systems to create tickets (e.g., from CRM, marketing automation).

---

### 3. **Agents Endpoints** (Support App - Agent Management)
```
GET   /api/agents
POST  /api/agents
GET   /api/agents/{agent_id}
PATCH /api/agents/{agent_id}
DELETE /api/agents/{agent_id}
POST  /api/agents/login
POST  /api/agents/logout
GET   /api/agents/me
PATCH /api/agents/me/status
```

**Analysis**: Pure **support app operations**. Should remain internal to Support App frontend. Not part of platform intelligence.

---

### 4. **Other Available Routers** (from main.py imports)
Not visible in Swagger but imported:

```python
from backend.api.routers import (
    admin_router,           # Admin operations
    health_router,          # Health checks
    customers_router,       # Customer data CRUD
    customer_alias_router,  # Customer aliases
    analytics_router,       # Analytics queries
    campaigns_router,       # Marketing campaigns
    mcp_router,             # MCP tool access
    webhooks_router,        # Webhook receivers
    segments_router,        # Segment queries
    system_router,          # System info
    tickets_router,         # (mapped to /api/tickets)
    ai_router,              # (mapped to /api/ai)
)
```

**Need to investigate**: segments_router, customers_router, analytics_router, mcp_router

---

## Platform Architecture Mapping

### **Platform Layer APIs** (Intelligence Brain - Expose to External Teams)
**Base path**: `/api/intelligence/*` and `/api/generation/*`

| Current Endpoint | New Platform API | Purpose | Schema |
|-----------------|------------------|---------|---------|
| `GET /api/ai/customers/{customer_id}/intelligence` | `POST /api/intelligence/analyze` | Behavioral analysis, churn, LTV, segments | `platform` |
| N/A | `POST /api/intelligence/predict/churn` | Churn prediction for customer | `platform` |
| N/A | `POST /api/intelligence/predict/ltv` | LTV forecasting | `platform` |
| `GET /api/ai/tickets/{ticket_id}/draft-response` | `POST /api/generation/message` | Generate AI response | `platform` |
| `GET /api/ai/tickets/{ticket_id}/recommendation` | `POST /api/generation/actions` | Generate recommended actions | `platform` |
| `POST /api/ai/tickets/{ticket_id}/regenerate-draft` | `POST /api/generation/message/regenerate` | Regenerate with new context | `platform` |

### **Support App APIs** (Operational - Internal to Support Frontend)
**Base path**: `/api/support/*`

| Current Endpoint | New Support API | Purpose | Schema |
|-----------------|-----------------|---------|---------|
| `GET /api/tickets` | `GET /api/support/tickets` | List tickets | `support_app` |
| `POST /api/tickets` | `POST /api/support/tickets` | Create ticket | `support_app` |
| `GET /api/tickets/{id}` | `GET /api/support/tickets/{id}` | Get ticket details | `support_app` |
| `POST /api/tickets/{id}/messages` | `POST /api/support/tickets/{id}/messages` | Send message | `support_app` |
| Agent endpoints | `/api/support/agents/*` | Agent management | `support_app` |

---

## What External Teams Should Use

### **Customer Support Frontends** (e.g., Gorgias, Zendesk, Custom UI)
**Use Platform APIs**:
1. `POST /api/intelligence/analyze` - Get customer intelligence panel
2. `POST /api/generation/message` - Get AI draft responses
3. `POST /api/generation/actions` - Get recommended actions

**Optionally expose**:
- `POST /api/support/tickets` - Create tickets from external systems

### **CRM Systems** (e.g., Salesforce, HubSpot)
**Use Platform APIs**:
1. `POST /api/intelligence/analyze` - Enrich customer records with AI insights
2. `POST /api/intelligence/predict/churn` - Get churn risk for proactive outreach
3. `POST /api/intelligence/predict/ltv` - Prioritize high-value customers

### **Marketing Automation** (e.g., Klaviyo, Customer.io)
**Use Platform APIs**:
1. `POST /api/intelligence/analyze` - Segment customers for campaigns
2. `POST /api/intelligence/predict/churn` - Target at-risk customers
3. `POST /api/generation/message` - Generate personalized messages

---

## Missing Platform APIs

Based on API_REQUIREMENTS.md, we need to create:

### Intelligence APIs
- [ ] `POST /api/intelligence/analyze` - Customer behavioral analysis
- [ ] `POST /api/intelligence/predict/churn` - Churn prediction
- [ ] `POST /api/intelligence/predict/ltv` - LTV forecasting
- [ ] `GET /api/intelligence/segments/stats` - Segment distribution stats
- [ ] `GET /api/intelligence/archetypes` - List available archetypes

### Generation APIs
- [ ] `POST /api/generation/message` - Generate AI message
- [ ] `POST /api/generation/actions` - Generate recommended actions
- [ ] `POST /api/generation/campaign` - Generate campaign content

### Current implementations to refactor:
- [x] `GET /api/ai/customers/{customer_id}/intelligence` exists - needs RESTful refactor
- [x] `GET /api/ai/tickets/{ticket_id}/draft-response` exists - needs RESTful refactor
- [x] `GET /api/ai/tickets/{ticket_id}/recommendation` exists - needs RESTful refactor

---

## Authentication for External Teams

**Current**:
- `X-API-Key` header with ADMIN_KEY
- Applied via `require_api_key` dependency

**Needed for platform**:
- Tenant-specific API keys (per company)
- Rate limiting per tenant
- Usage tracking per tenant

**Implementation status**:
- [x] Basic API key auth exists
- [ ] Tenant-specific keys (multi-tenancy)
- [ ] Rate limiting by tenant
- [ ] Usage metrics

---

## Next Steps (Week 2)

1. **Create Platform Intelligence Router** (`backend/platform/intelligence.py`)
   - Implement `/api/intelligence/analyze`
   - Implement `/api/intelligence/predict/churn`
   - Implement `/api/intelligence/predict/ltv`
   - Implement `/api/intelligence/segments/stats`

2. **Create Platform Generation Router** (`backend/platform/generation.py`)
   - Implement `/api/generation/message`
   - Implement `/api/generation/actions`
   - Use existing AI logic from `ai_router.py`

3. **Refactor existing AI endpoints**
   - Keep `/api/ai/*` for backward compatibility
   - Make them call platform APIs internally
   - Add deprecation warnings

4. **Update Swagger documentation**
   - Tag platform APIs as "Platform Intelligence" and "Platform Generation"
   - Tag support APIs as "Support App (Internal)"
   - Add clear descriptions for external teams

5. **Update API_REQUIREMENTS.md**
   - Add real examples from Swagger UI
   - Document actual request/response schemas
   - Add authentication flow examples

---

## Summary

**Current State**:
- Mixed platform intelligence and operational endpoints
- Intelligence APIs exist but under `/api/ai/*` (not RESTful)
- No clear separation for external teams

**Target State**:
- Clean `/api/intelligence/*` and `/api/generation/*` for platform brain
- Internal `/api/support/*` for support app operations
- Clear API documentation showing what external teams should consume
- Tenant-specific API keys and rate limiting

**Key Insight**:
The intelligence capabilities already exist in the codebase. Week 2 is about **reorganizing and exposing** them through clean platform APIs, not building new AI features.
