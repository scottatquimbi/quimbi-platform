# Customer Support Backend - Architecture Document

## System Overview

The **Customer Support Backend** is the operational CRM system for managing customer support tickets, agents, and workflows. It focuses on business operations and integrates with the **Quimbi Backend** for AI/ML intelligence.

## Design Philosophy

### Separation of Concerns

```
Quimbi Backend = "What does the AI think about this customer?"
Support Backend = "How do we operationally handle this ticket?"
```

- **Quimbi Backend**: Stateless AI/ML engine providing intelligence
- **Support Backend**: Stateful operational system managing workflows

## Architecture Diagram

```
┌──────────────────────────┐
│   Support Frontend       │
│   (Agent UI)             │
└───────────┬──────────────┘
            │
            ▼
┌────────────────────────────────┐
│  CUSTOMER SUPPORT BACKEND      │
│  (This System)                 │
│                                │
│  Core Domains:                 │
│  • Tickets                     │
│  • Customers                   │
│  • Agents                      │
│  • Assignments                 │
│  • SLA Tracking                │
│  • Integrations                │
│                                │
│  Calls Quimbi for AI:          │
│  • Customer DNA        ────────┼───┐
│  • Churn Prediction    ────────┼───┤
│  • AI Drafts           ────────┼───┤
│  • Recommendations     ────────┼───┤
└────────────────────────────────┘   │
                                     │
                                     ▼
                        ┌─────────────────────────┐
                        │  QUIMBI BACKEND         │
                        │  (AI/ML Engine)         │
                        │                         │
                        │  • 13-Axis DNA          │
                        │  • Churn ML Models      │
                        │  • LTV Forecasting      │
                        │  • AI Generation        │
                        │  • Segmentation         │
                        └─────────────────────────┘
```

## Domain Model

### Core Entities (Owned by Support Backend)

#### 1. **Customers**
- Contact information (email, phone, name)
- Shopify customer ID (external reference)
- Timezone, language preferences
- Account creation date
- **Does NOT store**: DNA, segments, churn predictions (fetched from Quimbi)

#### 2. **Tickets**
- Subject, description, status, priority
- Channel (email, chat, phone, SMS)
- Customer reference
- Created/updated timestamps
- Tags, categories
- **Enriched with**: AI insights from Quimbi when displayed

#### 3. **Messages**
- Conversation thread within tickets
- Content, sender (agent or customer)
- Attachments
- **Enriched with**: Sentiment scores from Quimbi

#### 4. **Agents**
- Support team members
- Roles, permissions, departments
- Availability status (online, busy, offline)
- Specializations (technical, billing, VIP)
- Performance metrics

#### 5. **Ticket Assignments**
- Links tickets to agents
- Assignment timestamp, reason (manual, auto, transfer)
- Workload tracking
- Transfer history

#### 6. **SLA Tracking**
- Response time targets by priority
- Resolution time targets
- Breach detection and alerting
- Pause/resume for "pending customer" status

#### 7. **Notes**
- Internal agent-only comments
- Not visible to customers
- Collaboration, context sharing

## Integration Points

### External Systems

#### **Quimbi Backend** (AI/ML Intelligence)
- **Direction**: Support Backend → Quimbi (outbound calls)
- **Authentication**: X-API-Key header
- **Endpoints Used**:
  - `POST /api/ml/customer/analyze` - Get customer DNA
  - `POST /api/ml/churn/predict` - Get churn risk
  - `POST /api/ml/generate/draft` - Generate AI draft
  - `POST /api/ml/recommend/actions` - Get next best actions

#### **Shopify** (E-commerce Platform)
- **Direction**: Bidirectional
- **Purpose**:
  - Import customer data
  - Fetch order history
  - Product information for support context
- **Integration Type**: REST API + Webhooks

#### **Gorgias** (Help Desk Platform)
- **Direction**: Bidirectional
- **Purpose**:
  - Ingest tickets from Gorgias
  - Sync ticket updates back
  - Real-time webhook events
- **Integration Type**: REST API + Webhooks

#### **Slack** (Team Communication)
- **Direction**: Outbound
- **Purpose**:
  - SLA breach notifications
  - Urgent ticket alerts
  - Agent mentions
- **Integration Type**: Webhooks + Bot API

## API Design

### RESTful Endpoints

#### Tickets
```
POST   /api/tickets                      Create ticket
GET    /api/tickets                      List tickets (with smart ordering)
GET    /api/tickets/{id}                 Get ticket details (enriched with AI)
PATCH  /api/tickets/{id}                 Update ticket
DELETE /api/tickets/{id}                 Close/archive ticket

POST   /api/tickets/{id}/messages        Add message
GET    /api/tickets/{id}/messages        List messages
POST   /api/tickets/{id}/notes           Add internal note
GET    /api/tickets/{id}/notes           List notes
```

#### Customers
```
POST   /api/customers                    Create/import customer
GET    /api/customers                    List customers
GET    /api/customers/{id}               Get customer (enriched with DNA from Quimbi)
PATCH  /api/customers/{id}               Update customer
GET    /api/customers/{id}/tickets       Get customer's ticket history
```

#### Agents
```
POST   /api/agents                       Create agent
GET    /api/agents                       List agents
GET    /api/agents/{id}                  Get agent details
PATCH  /api/agents/{id}                  Update agent
POST   /api/agents/{id}/login            Agent login
POST   /api/agents/{id}/logout           Agent logout
GET    /api/agents/{id}/queue            Get agent's ticket queue
```

#### Assignments
```
POST   /api/tickets/{id}/assign          Manually assign ticket
POST   /api/tickets/{id}/auto-assign     Smart auto-assignment
POST   /api/tickets/{id}/transfer        Transfer to another agent
GET    /api/tickets/unassigned           List unassigned tickets
GET    /api/agents/available             List available agents
```

#### SLA
```
GET    /api/sla/policies                 List SLA policies
POST   /api/sla/policies                 Create policy
GET    /api/sla/tickets/{id}             Get SLA status
GET    /api/sla/breaches                 List breached tickets
GET    /api/sla/at-risk                  List tickets near breach
GET    /api/sla/dashboard                SLA metrics dashboard
```

#### AI Features (Proxied to Quimbi)
```
GET    /api/ai/tickets/{id}/draft        Get AI draft (calls Quimbi)
GET    /api/ai/tickets/{id}/recommend    Get AI recommendations (calls Quimbi)
GET    /api/ai/customers/{id}/dna        Get customer DNA (calls Quimbi)
GET    /api/ai/customers/{id}/churn      Get churn prediction (calls Quimbi)
```

### WebSocket Endpoints
```
WS     /ws/agent/{agent_id}              Agent real-time updates
       Events: new_ticket, ticket_update, sla_warning, agent_status
```

## Data Flow Examples

### Example 1: Agent Views Ticket

```
1. Frontend: GET /api/tickets/123

2. Support Backend:
   a. Fetch ticket from local DB (tickets table)
   b. Fetch assignment from local DB (assignments table)
   c. Fetch SLA status from local DB (sla_tracking table)
   d. Call Quimbi: POST /api/ml/customer/analyze
      - Send customer order history
      - Receive DNA profile, segments, archetype
   e. Call Quimbi: POST /api/ml/churn/predict
      - Send customer metrics
      - Receive churn risk, factors
   f. Combine all data into enriched response

3. Response to Frontend:
   {
     "ticket": {...ticket data...},
     "customer": {...customer data...},
     "assignment": {...assignment data...},
     "sla": {...SLA status...},
     "ai_insights": {
       "dna": {...from Quimbi...},
       "churn_risk": {...from Quimbi...}
     }
   }
```

### Example 2: Agent Generates AI Draft

```
1. Frontend: GET /api/ai/tickets/123/draft

2. Support Backend:
   a. Fetch ticket messages from local DB
   b. Fetch customer profile from local DB
   c. Call Quimbi: POST /api/ml/generate/draft
      Body: {
        "messages": [...],
        "customer_profile": {...},
        "channel": "email"
      }
   d. Return Quimbi's response to frontend

3. Response:
   {
     "draft": "Hi Sarah, I understand your concern...",
     "tone": "empathetic",
     "personalization": ["used_name", "referenced_order_123"]
   }
```

### Example 3: New Ticket Auto-Assignment

```
1. Ticket created (via API or Gorgias webhook)

2. Support Backend:
   a. Create ticket record in DB
   b. Create SLA tracking record
   c. Call Quimbi: POST /api/ml/customer/analyze
      - Get customer archetype
   d. Query local DB for available agents
   e. Run assignment algorithm:
      - Agent availability (not at capacity)
      - Specialization match (ticket category)
      - Customer tier (VIP → senior agents)
   f. Create assignment record
   g. Send WebSocket event to assigned agent
   h. Create Slack notification (if high priority)
```

## Technology Stack

### Core Framework
- **FastAPI** - Async Python web framework
- **Python 3.11+** - Language runtime
- **Uvicorn** - ASGI server

### Database
- **PostgreSQL** - Primary database
- **SQLAlchemy** - Async ORM
- **Alembic** - Database migrations

### Caching & Queue
- **Redis** - Caching layer + session storage
- **Celery** - Background job processing

### External Clients
- **httpx** - Async HTTP client (for Quimbi API)
- **shopify-python-api** - Shopify integration
- **gorgias-python** - Gorgias integration

### Real-Time
- **WebSockets** - Real-time agent updates
- **Server-Sent Events** - Alternative for one-way updates

### AI/ML Integration
- **No local AI libraries** - All AI via Quimbi Backend API

### Authentication
- **JWT** - Agent authentication tokens
- **OAuth2** - For external integrations (Shopify, Gorgias)

### Deployment
- **Docker** - Containerization
- **Railway** - PaaS hosting
- **GitHub Actions** - CI/CD

## Security Considerations

### Authentication & Authorization
- JWT tokens for agent sessions
- API keys for service-to-service (Quimbi integration)
- Role-based access control (RBAC) for agents
- OAuth2 for third-party integrations

### Data Protection
- Encrypt sensitive customer data at rest
- TLS for all API communication
- Audit logging for data access
- GDPR compliance (data deletion, export)

### Rate Limiting
- Per-agent rate limits on API endpoints
- Circuit breaker for Quimbi API calls
- Exponential backoff on retries

## Performance Optimization

### Caching Strategy
- **Redis Cache Layers**:
  - Customer profiles (TTL: 5 minutes)
  - Quimbi DNA responses (TTL: 15 minutes)
  - Ticket lists (invalidate on update)
  - Agent availability (TTL: 30 seconds)

### Database Optimization
- Indexes on frequently queried fields (ticket status, customer_id, agent_id)
- Connection pooling (max 20 connections)
- Read replicas for analytics queries (future)

### API Optimization
- Batch Quimbi API calls where possible
- Async/await for concurrent operations
- Pagination on list endpoints (max 100 items)
- Partial responses (allow client to specify fields)

## Monitoring & Observability

### Metrics
- Request latency (p50, p95, p99)
- Error rates by endpoint
- Quimbi API call success rate
- Database query performance
- WebSocket connection count
- Agent activity (tickets/hour, response times)

### Logging
- Structured JSON logs
- Request correlation IDs
- Error stack traces
- Audit trail for data changes

### Alerting
- SLA breach notifications
- API error rate spikes
- Database connection pool exhaustion
- Quimbi API downtime

## Future Considerations

### Phase 2 Features
- Multi-channel support (voice, video)
- Customer self-service portal
- Knowledge base integration
- Macros & saved replies
- Ticket automation rules

### Phase 3 Features
- Mobile app for agents
- Analytics dashboard
- Customer satisfaction (CSAT) surveys
- Agent performance leaderboard
- Advanced reporting

### Scalability
- Horizontal scaling (multiple backend instances)
- Database sharding by tenant (multi-tenancy)
- Event-driven architecture (message queue)
- Microservices decomposition (if needed)

## Decision Log

### Why Separate from Quimbi Backend?
- **Clarity**: Clear separation between AI/ML (Quimbi) and operations (Support)
- **Scalability**: Different scaling needs (compute vs. transactions)
- **Team Structure**: Data scientists vs. full-stack engineers
- **Technology Fit**: Python ML ecosystem vs. operational CRUD

### Why PostgreSQL?
- Mature, reliable, well-understood
- Excellent JSON support (for flexible fields)
- Strong consistency guarantees
- Good performance for transactional workload

### Why FastAPI?
- Async/await support (concurrent Quimbi calls)
- Automatic OpenAPI documentation
- Pydantic validation (type safety)
- Modern Python, good developer experience

### Why Redis?
- Fast in-memory cache
- Supports complex data structures
- Celery task queue broker
- Session storage

## API Contract with Quimbi Backend

See `docs/quimbi-integration.md` for detailed API specifications.

## Contributing

See `CONTRIBUTING.md` for development guidelines.

## License

Proprietary - Quimbi.ai
