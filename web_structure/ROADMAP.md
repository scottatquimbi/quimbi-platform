# Customer Support Backend - Development Roadmap

## Vision

Build a full-featured operational CRM for customer support that leverages Quimbi Backend for AI/ML intelligence while owning all operational workflows, team management, and business logic.

---

## Phase 1: Foundation & Quimbi Integration (Weeks 1-3)

### Week 1: Infrastructure Setup

**Goal**: Establish core infrastructure and Quimbi integration

#### Tasks:

1. **Create Quimbi Client Service**
   ```python
   # File: app/services/quimbi_client.py
   ```
   - [ ] HTTP client wrapper with retry logic
   - [ ] Circuit breaker pattern
   - [ ] Request/response logging
   - [ ] Error handling with custom exceptions
   - [ ] Unit tests with mocked Quimbi responses

2. **Update Configuration**
   ```python
   # File: app/core/config.py
   ```
   - [ ] Add `quimbi_backend_url`
   - [ ] Add `quimbi_api_key`
   - [ ] Add Quimbi-specific settings (timeout, retries)
   - [ ] Environment variable validation

3. **Database Migration Setup**
   - [ ] Initialize Alembic
   - [ ] Create initial migration
   - [ ] Document migration workflow

4. **Replace Mock AI Service**
   ```python
   # File: app/api/ai.py
   ```
   - [ ] Delete mock functions (lines 128-206)
   - [ ] Integrate Quimbi client
   - [ ] Add error handling for Quimbi API failures
   - [ ] Add fallback behavior when Quimbi is unavailable

**Deliverables**:
- ✅ Quimbi integration working end-to-end
- ✅ AI draft generation from Quimbi
- ✅ Customer DNA profiles from Quimbi
- ✅ Churn predictions from Quimbi

---

### Week 2: Core Data Models

**Goal**: Build foundational database models for operational CRM

#### Tasks:

1. **Customer Model (Enhanced)**
   ```python
   # File: app/models/customer.py
   ```
   - [ ] Basic fields (id, email, name, phone)
   - [ ] External references (shopify_customer_id)
   - [ ] Preferences (language, timezone, communication_channel)
   - [ ] Metadata (created_at, updated_at, last_contact_at)
   - [ ] Relationship to tickets

2. **Ticket Model (Keep Existing, Enhance)**
   ```python
   # File: app/models/ticket.py
   ```
   - [ ] Keep existing fields
   - [ ] Add tags (JSON array)
   - [ ] Add category (auto-categorization from Quimbi)
   - [ ] Add metadata (source, utm_params, referrer)
   - [ ] Soft delete support

3. **Message Model (Enhanced)**
   ```python
   # File: app/models/message.py
   ```
   - [ ] Add attachments support (JSON array of URLs)
   - [ ] Add read status
   - [ ] Add delivery status (for emails)
   - [ ] Add rich text/HTML support

4. **Create Database Migration**
   ```bash
   alembic revision --autogenerate -m "Core CRM models"
   alembic upgrade head
   ```

**Deliverables**:
- ✅ Customer, Ticket, Message models finalized
- ✅ Database migrations created and tested
- ✅ Relationships properly defined

---

### Week 3: Ticket Management API

**Goal**: Build complete ticket CRUD with Quimbi enrichment

#### Tasks:

1. **Ticket Endpoints (Refactor Existing)**
   ```python
   # File: app/api/tickets.py
   ```
   - [ ] `POST /api/tickets` - Create with validation
   - [ ] `GET /api/tickets` - List with smart ordering
   - [ ] `GET /api/tickets/{id}` - Get with Quimbi enrichment
   - [ ] `PATCH /api/tickets/{id}` - Update
   - [ ] `DELETE /api/tickets/{id}` - Soft delete
   - [ ] Add filtering (status, priority, channel, customer_id)
   - [ ] Add search (subject, content)

2. **Message Endpoints**
   ```python
   # File: app/api/messages.py
   ```
   - [ ] `POST /api/tickets/{id}/messages` - Add message
   - [ ] `GET /api/tickets/{id}/messages` - List messages
   - [ ] `PATCH /api/messages/{id}` - Edit message
   - [ ] `DELETE /api/messages/{id}` - Soft delete
   - [ ] Handle attachments

3. **Ticket Enrichment Service**
   ```python
   # File: app/services/enrichment.py
   ```
   - [ ] Fetch customer DNA from Quimbi
   - [ ] Fetch churn prediction from Quimbi
   - [ ] Fetch AI-suggested category
   - [ ] Combine with local ticket data
   - [ ] Cache enriched data (Redis)

4. **Scoring Service (Keep, Enhance)**
   ```python
   # File: app/services/scoring_service.py
   ```
   - [ ] Integrate Quimbi churn/LTV data
   - [ ] Keep existing scoring logic
   - [ ] Add caching for scores

**Deliverables**:
- ✅ Full ticket CRUD working
- ✅ Tickets enriched with Quimbi AI data
- ✅ Smart ordering with real churn/LTV
- ✅ Message threading working

---

## Phase 2: Agent Management (Weeks 4-6)

### Week 4: Agent Models & Authentication

**Goal**: Build agent management system with authentication

#### Tasks:

1. **Agent Model**
   ```python
   # File: app/models/agent.py
   ```
   - [ ] Create Agent table (id, email, name, role, department)
   - [ ] Add hashed_password field
   - [ ] Add status (online, busy, offline, away)
   - [ ] Add availability settings (max_concurrent_tickets, accepts_new)
   - [ ] Add specializations (JSON array)
   - [ ] Add performance tracking fields

2. **Authentication Service**
   ```python
   # File: app/services/auth.py
   ```
   - [ ] Password hashing (bcrypt)
   - [ ] JWT token generation
   - [ ] Token verification
   - [ ] Get current agent from token
   - [ ] Role-based permissions (RBAC)

3. **Agent Endpoints**
   ```python
   # File: app/api/agents.py
   ```
   - [ ] `POST /api/agents` - Create agent (admin only)
   - [ ] `GET /api/agents` - List agents
   - [ ] `GET /api/agents/{id}` - Get agent details
   - [ ] `PATCH /api/agents/{id}` - Update agent
   - [ ] `DELETE /api/agents/{id}` - Deactivate agent
   - [ ] `POST /api/auth/login` - Agent login
   - [ ] `POST /api/auth/logout` - Agent logout
   - [ ] `GET /api/auth/me` - Get current agent

4. **Protect Existing Endpoints**
   - [ ] Add `Depends(get_current_agent)` to ticket endpoints
   - [ ] Add role checks where needed
   - [ ] Update tests with authentication

**Deliverables**:
- ✅ Agent management working
- ✅ JWT authentication implemented
- ✅ Protected endpoints
- ✅ Login/logout flow

---

### Week 5: Ticket Assignment

**Goal**: Build smart ticket assignment system

#### Tasks:

1. **Assignment Model**
   ```python
   # File: app/models/assignment.py
   ```
   - [ ] Create TicketAssignment table
   - [ ] Track assignment history
   - [ ] Track transfer history
   - [ ] Add assignment status (assigned, accepted, in_progress, completed)

2. **Assignment Service**
   ```python
   # File: app/services/assignment.py
   ```
   - [ ] Auto-assignment algorithm:
     - Agent availability
     - Workload balancing
     - Specialization matching
     - Customer tier (VIP → senior agents)
     - Language matching
   - [ ] Manual assignment validation
   - [ ] Transfer logic
   - [ ] Workload calculation

3. **Assignment Endpoints**
   ```python
   # File: app/api/assignments.py
   ```
   - [ ] `POST /api/tickets/{id}/assign` - Manual assign
   - [ ] `POST /api/tickets/{id}/auto-assign` - Smart assign
   - [ ] `POST /api/tickets/{id}/transfer` - Transfer ticket
   - [ ] `POST /api/tickets/{id}/accept` - Agent accepts
   - [ ] `GET /api/agents/{id}/queue` - Agent's queue
   - [ ] `GET /api/tickets/unassigned` - Unassigned tickets

4. **Agent Queue View**
   - [ ] Fetch assigned tickets
   - [ ] Enrich with Quimbi data
   - [ ] Sort by priority (SLA urgency, customer value)
   - [ ] Show workload metrics

**Deliverables**:
- ✅ Manual assignment working
- ✅ Auto-assignment algorithm implemented
- ✅ Agent queue view
- ✅ Transfer functionality

---

### Week 6: SLA Tracking

**Goal**: Implement SLA tracking and breach alerting

#### Tasks:

1. **SLA Models**
   ```python
   # File: app/models/sla.py
   ```
   - [ ] Create SLAPolicy table (by priority)
   - [ ] Create SLATracking table (per ticket)
   - [ ] Track first response time
   - [ ] Track resolution time
   - [ ] Track breach status

2. **SLA Service**
   ```python
   # File: app/services/sla.py
   ```
   - [ ] Calculate elapsed time
   - [ ] Calculate remaining time
   - [ ] Detect breaches
   - [ ] Pause/resume for "pending customer" status
   - [ ] Business hours calculation

3. **SLA Endpoints**
   ```python
   # File: app/api/sla.py
   ```
   - [ ] `GET /api/sla/policies` - List policies
   - [ ] `POST /api/sla/policies` - Create policy
   - [ ] `GET /api/sla/tickets/{id}` - Get SLA status
   - [ ] `GET /api/sla/breaches` - List breaches
   - [ ] `GET /api/sla/at-risk` - Tickets near breach
   - [ ] `GET /api/sla/dashboard` - Metrics

4. **Background SLA Monitor (Celery)**
   ```python
   # File: app/tasks/sla_monitor.py
   ```
   - [ ] Setup Celery with Redis broker
   - [ ] Create periodic task (runs every minute)
   - [ ] Check for breaches
   - [ ] Send alerts (WebSocket, email, Slack)
   - [ ] Update breach status in DB

**Deliverables**:
- ✅ SLA policies configured
- ✅ Real-time SLA tracking
- ✅ Breach detection working
- ✅ Alerts sent to agents

---

## Phase 3: Integrations (Weeks 7-9)

### Week 7: Shopify Integration

**Goal**: Import customer and order data from Shopify

#### Tasks:

1. **Shopify Client**
   ```python
   # File: app/integrations/shopify_client.py
   ```
   - [ ] OAuth2 authentication
   - [ ] Customer API client
   - [ ] Order API client
   - [ ] Product API client
   - [ ] Webhook verification

2. **Customer Sync**
   - [ ] Import Shopify customers
   - [ ] Map Shopify fields to our model
   - [ ] Handle updates (webhook)
   - [ ] Deduplicate by email

3. **Order Context**
   - [ ] Fetch customer orders on demand
   - [ ] Cache order data (Redis)
   - [ ] Display in ticket view
   - [ ] Use for AI draft generation context

4. **Shopify Endpoints**
   ```python
   # File: app/api/shopify.py
   ```
   - [ ] `POST /api/shopify/sync/customers` - Import customers
   - [ ] `POST /api/shopify/webhooks/customers` - Webhook handler
   - [ ] `POST /api/shopify/webhooks/orders` - Webhook handler
   - [ ] `GET /api/customers/{id}/orders` - Get customer orders

**Deliverables**:
- ✅ Shopify integration working
- ✅ Customer data synced
- ✅ Order history available
- ✅ Webhooks handling updates

---

### Week 8: Gorgias Integration

**Goal**: Bi-directional ticket sync with Gorgias

#### Tasks:

1. **Gorgias Client**
   ```python
   # File: app/integrations/gorgias_client.py
   ```
   - [ ] API authentication
   - [ ] Ticket API client
   - [ ] Message API client
   - [ ] Customer API client
   - [ ] Webhook verification

2. **Ticket Import**
   - [ ] Import existing Gorgias tickets
   - [ ] Map Gorgias fields to our model
   - [ ] Handle message threading
   - [ ] Link to customers

3. **Ticket Sync**
   - [ ] Push new tickets to Gorgias
   - [ ] Push message updates to Gorgias
   - [ ] Handle Gorgias webhooks (new messages)
   - [ ] Sync status changes

4. **Gorgias Endpoints**
   ```python
   # File: app/api/gorgias.py
   ```
   - [ ] `POST /api/gorgias/sync/tickets` - Import tickets
   - [ ] `POST /api/gorgias/webhooks/ticket-message-created`
   - [ ] `POST /api/gorgias/webhooks/ticket-created`
   - [ ] `GET /api/tickets/{id}/gorgias-link` - Get Gorgias URL

**Deliverables**:
- ✅ Gorgias integration working
- ✅ Tickets synced from Gorgias
- ✅ Bi-directional message sync
- ✅ Webhooks handling real-time updates

---

### Week 9: Slack Integration

**Goal**: Send notifications and alerts to Slack

#### Tasks:

1. **Slack Client**
   ```python
   # File: app/integrations/slack_client.py
   ```
   - [ ] Webhook notifications
   - [ ] Bot API (optional, for interactive messages)
   - [ ] Channel management
   - [ ] User mentions

2. **Notification Types**
   - [ ] SLA breach alerts
   - [ ] New urgent tickets
   - [ ] Agent mentions in notes
   - [ ] Customer churn risk warnings
   - [ ] Daily/weekly summaries

3. **Slack Endpoints**
   ```python
   # File: app/api/slack.py
   ```
   - [ ] `POST /api/slack/notify` - Send notification
   - [ ] `POST /api/slack/webhooks/events` - Handle Slack events
   - [ ] `GET /api/slack/channels` - List channels

4. **Background Notifications (Celery)**
   - [ ] Queue Slack notifications
   - [ ] Batch notifications (avoid spam)
   - [ ] Retry failed sends

**Deliverables**:
- ✅ Slack notifications working
- ✅ SLA breaches sent to Slack
- ✅ Urgent ticket alerts
- ✅ Daily summaries

---

## Phase 4: Real-Time & Caching (Weeks 10-11)

### Week 10: WebSocket Support

**Goal**: Real-time updates for agents

#### Tasks:

1. **WebSocket Infrastructure**
   ```python
   # File: app/websockets/connection.py
   ```
   - [ ] WebSocket endpoint per agent
   - [ ] Connection manager
   - [ ] Heartbeat/ping-pong
   - [ ] Reconnection handling

2. **Event Broadcasting**
   ```python
   # File: app/websockets/events.py
   ```
   - [ ] new_ticket - New assignment
   - [ ] ticket_update - Status changed
   - [ ] message_received - Customer replied
   - [ ] sla_warning - Approaching breach
   - [ ] agent_status - Another agent online/offline

3. **Agent Presence**
   ```python
   # File: app/services/presence.py
   ```
   - [ ] Track online agents
   - [ ] Update status (online, busy, away, offline)
   - [ ] Broadcast presence changes
   - [ ] Idle detection

4. **WebSocket Endpoints**
   ```python
   # File: app/websockets/main.py
   ```
   - [ ] `WS /ws/agent/{agent_id}` - Agent connection
   - [ ] Handle incoming events
   - [ ] Send outgoing events

**Deliverables**:
- ✅ WebSocket connections stable
- ✅ Real-time ticket updates
- ✅ Agent presence working
- ✅ SLA warnings pushed in real-time

---

### Week 11: Redis Caching

**Goal**: Improve performance with caching

#### Tasks:

1. **Cache Service**
   ```python
   # File: app/services/cache.py
   ```
   - [ ] Redis connection management
   - [ ] Cache key naming convention
   - [ ] TTL management
   - [ ] Cache invalidation

2. **Caching Layers**
   - [ ] Customer profiles (TTL: 5 min)
   - [ ] Quimbi DNA responses (TTL: 15 min)
   - [ ] Ticket lists (invalidate on update)
   - [ ] Agent availability (TTL: 30 sec)
   - [ ] AI drafts (TTL: 1 hour)

3. **Cache Patterns**
   - [ ] Read-through cache
   - [ ] Write-through cache
   - [ ] Cache-aside pattern
   - [ ] Cache warming

4. **Cache Monitoring**
   - [ ] Hit/miss rates
   - [ ] Cache size
   - [ ] Eviction metrics
   - [ ] Performance impact

**Deliverables**:
- ✅ Redis caching implemented
- ✅ API response times improved
- ✅ Reduced Quimbi API calls
- ✅ Cache monitoring

---

## Phase 5: Analytics & Reporting (Weeks 12-13)

### Week 12: Agent Performance

**Goal**: Track and display agent performance metrics

#### Tasks:

1. **Metrics Models**
   ```python
   # File: app/models/agent_metrics.py
   ```
   - [ ] Create AgentDailyMetrics table
   - [ ] Track ticket counts (assigned, resolved, transferred)
   - [ ] Track timing (avg response time, avg resolution time)
   - [ ] Track SLA compliance
   - [ ] Track activity (messages sent, notes added, online time)

2. **Metrics Collection**
   ```python
   # File: app/services/metrics.py
   ```
   - [ ] Calculate daily metrics
   - [ ] Aggregate weekly/monthly
   - [ ] Background job to compute metrics
   - [ ] Store in database

3. **Analytics Endpoints**
   ```python
   # File: app/api/analytics.py
   ```
   - [ ] `GET /api/analytics/agents/{id}` - Agent performance
   - [ ] `GET /api/analytics/agents/{id}/today` - Today's metrics
   - [ ] `GET /api/analytics/team` - Team-wide metrics
   - [ ] `GET /api/analytics/leaderboard` - Top performers
   - [ ] Date range filtering

**Deliverables**:
- ✅ Agent performance tracking
- ✅ Metrics dashboard data
- ✅ Leaderboard functionality

---

### Week 13: Support Analytics

**Goal**: Insights into support operations

#### Tasks:

1. **Support Metrics**
   - [ ] Ticket volume (daily, weekly, monthly)
   - [ ] Channel distribution (email, chat, phone)
   - [ ] Category distribution
   - [ ] Average resolution time
   - [ ] SLA compliance rate
   - [ ] Customer satisfaction (if available)

2. **Customer Insights**
   - [ ] Top customers by ticket count
   - [ ] High churn risk customers (from Quimbi)
   - [ ] VIP customer ticket resolution times
   - [ ] Repeat issues

3. **Analytics Endpoints**
   ```python
   # File: app/api/analytics.py (continued)
   ```
   - [ ] `GET /api/analytics/tickets/volume` - Ticket trends
   - [ ] `GET /api/analytics/tickets/channels` - Channel usage
   - [ ] `GET /api/analytics/tickets/categories` - Category breakdown
   - [ ] `GET /api/analytics/customers/churn` - Churn risk report
   - [ ] `GET /api/analytics/sla/compliance` - SLA metrics

**Deliverables**:
- ✅ Support analytics endpoints
- ✅ Ticket volume trends
- ✅ SLA compliance reporting
- ✅ Customer insights

---

## Phase 6: Polish & Production (Weeks 14-16)

### Week 14: Testing & QA

**Goal**: Comprehensive test coverage

#### Tasks:

1. **Unit Tests**
   - [ ] Test all services (95% coverage target)
   - [ ] Test all models
   - [ ] Test Quimbi client (mocked)
   - [ ] Test assignment algorithm
   - [ ] Test SLA calculations

2. **Integration Tests**
   - [ ] Test API endpoints (all CRUD operations)
   - [ ] Test authentication flows
   - [ ] Test WebSocket connections
   - [ ] Test webhook handlers
   - [ ] Test Quimbi integration (with test API)

3. **Load Testing**
   - [ ] Test concurrent agent connections
   - [ ] Test high ticket volume
   - [ ] Test Quimbi API failures (circuit breaker)
   - [ ] Test database under load
   - [ ] Test Redis cache under load

**Deliverables**:
- ✅ 90%+ test coverage
- ✅ All critical paths tested
- ✅ Load testing results documented

---

### Week 15: Monitoring & Observability

**Goal**: Production-ready monitoring

#### Tasks:

1. **Logging**
   ```python
   # File: app/core/logging.py
   ```
   - [ ] Structured JSON logging
   - [ ] Request correlation IDs
   - [ ] Error stack traces
   - [ ] Audit trail for data changes
   - [ ] Log levels (DEBUG, INFO, WARN, ERROR)

2. **Metrics**
   - [ ] Request latency (p50, p95, p99)
   - [ ] Error rates by endpoint
   - [ ] Quimbi API call success rate
   - [ ] Database query performance
   - [ ] WebSocket connection count
   - [ ] Cache hit rates

3. **Alerting**
   - [ ] SLA breach notifications
   - [ ] API error rate spikes
   - [ ] Database connection pool exhaustion
   - [ ] Quimbi API downtime
   - [ ] Disk/memory usage

4. **Observability Tools**
   - [ ] Set up Sentry (error tracking)
   - [ ] Set up DataDog/New Relic (APM) - optional
   - [ ] Health check endpoints
   - [ ] Prometheus metrics endpoint

**Deliverables**:
- ✅ Comprehensive logging
- ✅ Metrics collection
- ✅ Alerting configured
- ✅ Error tracking active

---

### Week 16: Documentation & Deployment

**Goal**: Production deployment and documentation

#### Tasks:

1. **API Documentation**
   - [ ] Complete OpenAPI descriptions
   - [ ] Add request/response examples
   - [ ] Document authentication
   - [ ] Document rate limits
   - [ ] Publish Swagger UI

2. **Deployment**
   - [ ] Railway production setup
   - [ ] Environment variables configured
   - [ ] Database migrations automated
   - [ ] CI/CD pipeline (GitHub Actions)
   - [ ] Staging environment

3. **Developer Documentation**
   - [ ] README with setup instructions
   - [ ] ARCHITECTURE.md (already created)
   - [ ] CONTRIBUTING.md (coding standards)
   - [ ] API integration guide
   - [ ] Troubleshooting guide

4. **Operational Documentation**
   - [ ] Deployment runbook
   - [ ] Incident response playbook
   - [ ] Scaling guide
   - [ ] Backup/restore procedures

**Deliverables**:
- ✅ Production deployment complete
- ✅ Documentation published
- ✅ CI/CD pipeline active
- ✅ Monitoring in production

---

## Post-Launch Roadmap

### Phase 7: Advanced Features (Months 4-6)

- [ ] Multi-tenant support (for multiple brands/companies)
- [ ] Customer self-service portal
- [ ] Knowledge base integration
- [ ] Macros & saved replies
- [ ] Ticket automation rules (auto-respond, auto-tag, auto-assign)
- [ ] Customer satisfaction (CSAT) surveys
- [ ] Agent performance leaderboard in UI
- [ ] Advanced reporting & dashboards
- [ ] Mobile app for agents
- [ ] Voice/video support channels

---

## Success Metrics

### Technical Metrics
- **API Response Time**: < 200ms (p95)
- **Test Coverage**: > 90%
- **Uptime**: 99.9%
- **Error Rate**: < 0.1%
- **Database Query Time**: < 50ms (p95)

### Business Metrics
- **First Response Time**: < 1 hour (p95)
- **Resolution Time**: < 24 hours (p95)
- **SLA Compliance**: > 95%
- **Agent Efficiency**: > 20 tickets/day per agent
- **Customer Satisfaction**: > 4.5/5

---

## Risk Management

### Technical Risks
- **Quimbi API Downtime**: Implement circuit breaker, fallback responses
- **Database Performance**: Connection pooling, read replicas, caching
- **WebSocket Scaling**: Use Redis pub/sub for multi-instance broadcasting
- **Data Migration**: Thorough testing, rollback plan, incremental migration

### Business Risks
- **Agent Adoption**: Comprehensive training, gradual rollout
- **Integration Failures**: Robust error handling, manual override options
- **Data Loss**: Automated backups, point-in-time recovery
- **Security Breach**: Encryption, access controls, audit logging

---

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1: Foundation | 3 weeks | Quimbi integration, core models, ticket API |
| Phase 2: Agent Mgmt | 3 weeks | Agents, auth, assignments, SLA |
| Phase 3: Integrations | 3 weeks | Shopify, Gorgias, Slack |
| Phase 4: Real-Time | 2 weeks | WebSocket, caching |
| Phase 5: Analytics | 2 weeks | Agent performance, support insights |
| Phase 6: Production | 3 weeks | Testing, monitoring, deployment |
| **Total** | **16 weeks (~4 months)** | **Production-ready CRM** |

---

## Next Steps

1. **Review & Approve Architecture** (This week)
   - Review ARCHITECTURE.md
   - Get team alignment on separation of concerns
   - Finalize technology choices

2. **Coordinate with Quimbi Team** (Week 1)
   - Discuss `/api/ml/` endpoint design
   - Get API key for integration
   - Set up test environment

3. **Begin Phase 1** (Week 1-3)
   - Start with Quimbi client implementation
   - Replace mock AI service
   - Test end-to-end integration

4. **Weekly Progress Reviews**
   - Demo completed features
   - Adjust timeline as needed
   - Prioritize based on business needs

---

**Let's build this! 🚀**
