# Architectural Decision Summary

## Decision: Separate AI/ML Backend from Operational CRM

**Date**: 2025-01-24
**Status**: ✅ Approved
**Impact**: High - Affects entire system architecture

---

## Context

We currently have:
1. **Quimbi Backend** - Full-featured platform with tickets, customers, AI generation, ML models
2. **Customer Support Backend** (this repo) - Started as duplicate ticketing system with mock AI

**Problem**: Unclear separation of responsibilities, duplicate features, mixed concerns

---

## Decision

**Split the system into two specialized backends:**

### **Quimbi Backend = AI/ML Intelligence Engine**
- **Purpose**: Provide AI/ML insights as a service
- **Responsibilities**:
  - 13-axis behavioral segmentation (Customer DNA)
  - Churn prediction ML models
  - LTV forecasting models
  - AI draft generation (Claude/GPT)
  - AI recommendations engine
  - Sentiment analysis
  - Intent detection
  - Category auto-classification
- **Data Storage**: Minimal (ML models, analytics cache, segment definitions)
- **Architecture**: Stateless API - pure functions that take data in, return insights
- **No Operational Data**: No tickets, no agents, no SLA tracking, no assignments

### **Customer Support Backend = Operational CRM**
- **Purpose**: Manage all customer support operations
- **Responsibilities**:
  - Full ticket lifecycle (CRUD, status, priority, routing)
  - Customer profiles (contact info, preferences, history)
  - Message threading (conversations, attachments)
  - Agent management (team, roles, permissions, availability)
  - Ticket assignments (manual, auto, transfers, workload)
  - SLA tracking (response times, resolution times, breaches)
  - Internal notes (agent collaboration)
  - Workflows (escalation, automation)
  - Integrations (Gorgias, Shopify, Slack)
- **Data Storage**: Full ownership (tickets, customers, agents, assignments, SLA records)
- **Architecture**: Stateful operational system
- **AI Integration**: Calls Quimbi Backend APIs for intelligence

---

## Rationale

### ✅ Benefits

1. **Clear Separation of Concerns**
   - Quimbi = "What does the AI think?"
   - Support Backend = "How do we handle this operationally?"
   - No confusion about ownership

2. **Independent Scaling**
   - Quimbi: Scale for compute (GPUs for ML training, CPU for inference)
   - Support: Scale for traffic (more web servers, database replicas)
   - Different scaling strategies for different needs

3. **Team Structure**
   - **Quimbi Team**: Data scientists, ML engineers focused on model accuracy
   - **Support Team**: Full-stack engineers focused on UX and workflows
   - Clear team boundaries and responsibilities

4. **Technology Optimization**
   - **Quimbi**: Python ML ecosystem (NumPy, Pandas, TensorFlow, PyTorch)
   - **Support**: Best tool for job (FastAPI, Django, Node.js - whatever fits)
   - No technology compromises

5. **Deployment Flexibility**
   - Deploy Quimbi on GPU instances for ML
   - Deploy Support on standard web servers
   - Different uptime requirements (Support needs 99.9%+, Quimbi can degrade gracefully)

6. **Easier Testing**
   - Test AI features independently with ML metrics
   - Test operational features with mocked AI responses
   - No interference between test suites

7. **API Reusability**
   - Quimbi becomes "Customer Intelligence API"
   - Can be used by multiple products (not just Support)
   - Future: Marketing automation, sales CRM, analytics platform

### ⚠️ Trade-offs

1. **More API Calls**
   - Every ticket view needs customer DNA → API call to Quimbi
   - **Mitigation**: Redis caching (TTL: 5-15 minutes)

2. **Network Latency**
   - Inter-service communication adds latency
   - **Mitigation**: Async API calls, batch requests, caching

3. **More Complex Deployment**
   - Two backends to deploy and monitor
   - **Mitigation**: Good DevOps practices, containerization, health checks

4. **Data Duplication**
   - Customer basic data in both systems
   - **Mitigation**: Support Backend is source of truth, Quimbi caches for analysis

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                  SUPPORT FRONTEND                        │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│           CUSTOMER SUPPORT BACKEND (This Repo)             │
│                   "Operational CRM"                        │
│                                                            │
│  Owns: Tickets, Customers, Agents, Assignments, SLA       │
│  Stores: All operational data in PostgreSQL               │
│  Calls: Quimbi Backend for AI insights                    │
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTP/REST
                           ▼
┌────────────────────────────────────────────────────────────┐
│              QUIMBI BACKEND (Intelligence API)             │
│                   "AI/ML Engine"                           │
│                                                            │
│  Provides: DNA, Churn Pred, LTV Forecast, AI Drafts       │
│  Stateless: Pure functions (data in → insights out)       │
│  Minimal Storage: ML models, analytics cache              │
└────────────────────────────────────────────────────────────┘
```

---

## API Contract

### Quimbi Backend Provides (New `/api/ml/` Namespace)

```python
# Customer Intelligence
POST /api/ml/customer/analyze
  Input: { customer_id, orders[], interactions[] }
  Output: { dna_profile, archetype, segments, confidence }

POST /api/ml/churn/predict
  Input: { customer_id, recent_behavior }
  Output: { churn_risk_score, risk_level, factors, recommendations }

POST /api/ml/ltv/forecast
  Input: { customer_id, months }
  Output: { forecasted_ltv, confidence_interval, factors }

# AI Generation
POST /api/ml/generate/draft
  Input: { messages[], customer_profile, channel }
  Output: { draft_content, tone, personalization[], reasoning }

POST /api/ml/recommend/actions
  Input: { ticket_context, customer_profile }
  Output: { recommended_actions[], priorities, warnings[], talking_points[] }

# Analysis
POST /api/ml/sentiment/analyze
  Input: { text, context }
  Output: { sentiment_score, emotion, confidence }

POST /api/ml/intent/detect
  Input: { message, conversation_history }
  Output: { intent, confidence, entities[] }

POST /api/ml/category/classify
  Input: { ticket_subject, ticket_content }
  Output: { category, confidence, tags[] }
```

### Support Backend Consumes

All endpoints above, plus:
- Caches responses (Redis, TTL: 5-15 min)
- Handles Quimbi downtime gracefully (circuit breaker)
- Enriches ticket views with AI insights
- Uses predictions for smart routing/prioritization

---

## Migration Strategy

### Current State
- Quimbi Backend has full ticketing system
- Support Backend has duplicate (partially built)

### Migration Path

#### Phase 1: Extract ML API (Weeks 1-2)
**In Quimbi Backend:**
- [ ] Create `/api/ml/` namespace with stateless endpoints
- [ ] Keep existing `/api/tickets/` for backward compatibility
- [ ] Document new ML API

**In Support Backend:**
- [ ] Create Quimbi client service
- [ ] Replace mock AI with Quimbi API calls
- [ ] Test end-to-end integration

#### Phase 2: Build Full CRM (Weeks 3-6)
**In Support Backend:**
- [ ] Enhance ticket models (tags, categories, metadata)
- [ ] Build agent management (auth, roles, teams)
- [ ] Build assignment system (auto-assign, transfers)
- [ ] Build SLA tracking (policies, monitoring, alerts)
- [ ] Keep using Quimbi's ticket storage temporarily

#### Phase 3: Data Migration (Weeks 7-8)
- [ ] Export tickets from Quimbi DB
- [ ] Import to Support Backend DB
- [ ] Switch frontend to Support Backend
- [ ] Test thoroughly (rollback plan ready)

#### Phase 4: Cleanup (Weeks 9-10)
**In Quimbi Backend:**
- [ ] Deprecate `/api/tickets/` endpoints
- [ ] Remove ticket storage tables
- [ ] Keep only ML/AI endpoints
- [ ] Optimize for compute workload

---

## Success Criteria

### Technical
- ✅ Clear API boundaries between backends
- ✅ < 200ms API response time (p95) for Support Backend
- ✅ < 500ms for Quimbi ML inference (p95)
- ✅ > 95% cache hit rate for Quimbi responses
- ✅ Circuit breaker prevents cascading failures
- ✅ 99.9% uptime for Support Backend

### Organizational
- ✅ Teams understand their domain ownership
- ✅ No duplicate code between backends
- ✅ Clear escalation path for issues
- ✅ Independent deployment schedules

### Business
- ✅ AI features work reliably
- ✅ Support operations unaffected by Quimbi downtime
- ✅ Can scale teams independently
- ✅ Can reuse Quimbi for other products

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Quimbi API downtime | Medium | High | Circuit breaker, fallback responses, caching |
| API latency | Medium | Medium | Aggressive caching, async calls, batch requests |
| Data sync issues | Low | High | Support Backend is source of truth, clear data ownership |
| Team coordination | Medium | Low | Clear API contracts, regular sync meetings |
| Migration complexity | Medium | High | Phased migration, thorough testing, rollback plan |

---

## Next Steps

### Immediate (This Week)
1. ✅ Review and approve this decision document
2. ✅ Review ARCHITECTURE.md and ROADMAP.md
3. ✅ Get team alignment on approach

### Week 1
1. [ ] Coordinate with Quimbi team on `/api/ml/` API design
2. [ ] Get Quimbi API key for integration
3. [ ] Create Quimbi client in Support Backend
4. [ ] Replace mock AI service with real Quimbi calls

### Week 2-3
1. [ ] Enhance ticket/customer models
2. [ ] Build ticket enrichment (combine local data + Quimbi insights)
3. [ ] Test end-to-end flow

### Week 4-6
1. [ ] Build agent management
2. [ ] Build assignment system
3. [ ] Build SLA tracking

---

## Related Documents

- **ARCHITECTURE.md** - Full system architecture
- **ROADMAP.md** - 16-week development plan
- **README.md** - Project overview
- **RAILWAY_DEPLOY.md** - Deployment guide

---

## Approval

**Decision Maker**: Scott Allen
**Date**: 2025-01-24
**Status**: ✅ Approved

**Stakeholders**:
- [ ] Quimbi Backend Team - Needs to review
- [ ] Support Backend Team - Needs to review
- [ ] Product Team - Needs to review
- [ ] DevOps Team - Needs to review

---

## Appendix: Comparison with Alternatives

### Alternative 1: Keep Everything in Quimbi Backend
**Rejected because:**
- Mixed concerns (AI/ML + operational CRM)
- Different scaling needs
- Team confusion about ownership
- Technology compromises

### Alternative 2: Support Backend Proxies All Requests
**Rejected because:**
- Support Backend adds no value (just a pass-through)
- Extra latency for no benefit
- Why have two backends if one does nothing?

### Alternative 3: Duplicate Everything (Two Independent Systems)
**Rejected because:**
- Data consistency nightmare
- Duplicate code maintenance
- Sync complexity
- No shared intelligence

### ✅ Chosen: Specialized Backends with Clear APIs
**Why:**
- Clear separation of concerns
- Each backend adds unique value
- Scales independently
- Minimal data duplication (only cached)
- API contract enforces clean boundaries
