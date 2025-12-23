# System Architecture Document

**Customer Intelligence Platform**
**Version**: 2.0
**Last Updated**: November 4, 2025
**Status**: Production (Single-Tenant)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Architecture Layers](#architecture-layers)
4. [Data Architecture](#data-architecture)
5. [Application Architecture](#application-architecture)
6. [Integration Architecture](#integration-architecture)
7. [Infrastructure Architecture](#infrastructure-architecture)
8. [Security Architecture](#security-architecture)
9. [Performance & Scalability](#performance--scalability)
10. [Observability & Monitoring](#observability--monitoring)
11. [Deployment Architecture](#deployment-architecture)
12. [Future Architecture](#future-architecture)

---

## Executive Summary

The Customer Intelligence Platform is an AI-powered e-commerce analytics system that provides behavioral segmentation, churn prediction, and natural language query capabilities. The platform integrates with customer support tools (Gorgias) to deliver personalized AI-generated responses enriched with customer analytics.

**Key Characteristics**:
- **Architecture Pattern**: Layered monolith with modular components
- **Deployment Model**: Single-tenant cloud-hosted (Railway)
- **Data Scale**: 1.2M+ transactions, 27K+ customers, 868 archetypes
- **Integration Model**: Webhook-based real-time processing
- **AI Stack**: Claude 3.5 Haiku for NL routing and response generation

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     External Integrations                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Gorgias  │  │  Slack   │  │ Shopify  │  │Azure SQL │       │
│  │ Webhooks │  │   Bot    │  │   API    │  │  Source  │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼─────────────┼─────────────┼─────────────┼──────────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer (FastAPI)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 API Gateway (backend/main.py)             │  │
│  │  • Rate Limiting (1000/hour)                              │  │
│  │  • Request Validation                                     │  │
│  │  • Correlation ID Middleware                              │  │
│  │  • Structured Logging                                     │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│  ┌────────────────────┴──────────────────────────────────────┐ │
│  │              Router Layer (backend/api/routers)           │ │
│  │  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌────────┐ │ │
│  │  │ Webhooks │  │ Analytics │  │    MCP    │  │ Admin  │ │ │
│  │  │  Router  │  │  Router   │  │  Router   │  │ Router │ │ │
│  │  └──────────┘  └───────────┘  └───────────┘  └────────┘ │ │
│  └────────────────────┬──────────────────────────────────────┘ │
└────────────────────────┼──────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              AI Integration Components                      │ │
│  │  ┌──────────────────────┐  ┌──────────────────────────┐   │ │
│  │  │ Gorgias AI Assistant │  │  Natural Language Router │   │ │
│  │  │ • Webhook Handler    │  │  • Intent Classification │   │ │
│  │  │ • Source Detection   │  │  • Function Calling      │   │ │
│  │  │ • Response Generator │  │  • Context Management    │   │ │
│  │  └──────────────────────┘  └──────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              MCP Server (mcp_server/)                       │ │
│  │  8 Analytics Tools:                                         │ │
│  │  • analyze_customers    • analyze_segments                  │ │
│  │  • analyze_products     • forecast_metrics                  │ │
│  │  • target_campaign      • lookup_customer                   │ │
│  │  • analyze_behavior     • get_recommendations               │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Access Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Redis Cache  │  │ Query Layer  │  │  Connection  │         │
│  │  (Optional)  │  │  (SQL/ORM)   │  │     Pool     │         │
│  │  10-20x ↑    │  │              │  │   Max: 30    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer (PostgreSQL)                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Star Schema: fact_customer_current (27K rows)             │ │
│  │               combined_sales (1.2M rows)                    │ │
│  │               customer_profiles (27K rows)                  │ │
│  │               archetypes (868 behavioral cohorts)           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   External AI Services                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Anthropic Claude API (claude-3-5-haiku-20241022)         │  │
│  │  • Natural Language Understanding                          │  │
│  │  • Response Generation (max_tokens: 600)                   │  │
│  │  • Function Calling for Tool Routing                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture Layers

### 1. External Integration Layer

**Purpose**: Inbound webhook receivers and outbound API clients

**Components**:
- **Gorgias Webhook Receiver** (`/api/gorgias/webhook`)
  - HMAC-SHA256 signature verification
  - Rate limit: 1000/hour
  - Processes ticket creation/update events

- **Slack Bot Integration** (`/api/slack/events`)
  - Event API for @mentions and DMs
  - Slash commands (`/churn-check`, etc.)
  - Block Kit response formatting

- **Shopify Data Sync**
  - Automated daily sync from Azure SQL
  - Incremental updates via timestamp tracking

**Technology Stack**:
- FastAPI async endpoints
- HTTPX async HTTP client
- SlowAPI rate limiting

### 2. API Gateway Layer

**Purpose**: Request routing, validation, and cross-cutting concerns

**Middleware Pipeline**:
1. **CORS Middleware** - Cross-origin request handling
2. **Correlation ID Middleware** - Request tracking (X-Correlation-ID)
3. **Rate Limiting Middleware** - SlowAPI (per-IP, per-endpoint)
4. **Error Handling Middleware** - Standardized error responses
5. **Metrics Middleware** (Optional) - Prometheus metrics collection

**Key Features**:
- Structured JSON logging with correlation IDs
- Request/response logging with duration tracking
- Automatic error sanitization (no sensitive data in logs)

### 3. Business Logic Layer

**Purpose**: Core business logic and AI orchestration

**Key Components**:

#### Gorgias AI Assistant
- **Source Detection**: Identifies ticket origin (RingCentral, SMS, email, chat)
- **Filtering Logic**: Skips automation, closed tickets, outgoing messages
- **Tag-Based Control**: Respects `ai_ignore`, `force-ai` tags
- **Analytics Enrichment**: Fetches customer LTV, churn risk, purchase history
- **Response Generation**: Claude Haiku with source-specific prompts
- **Internal Note Posting**: Posts AI response as internal note for agent review

#### Natural Language Router
- **Intent Classification**: Uses Claude function calling
- **Tool Selection**: Routes to appropriate MCP tool
- **Context Management**: Maintains multi-turn conversation state
- **Response Formatting**: Converts tool outputs to natural language

#### MCP Server
- **8 Analytics Tools**: Customer, segment, product, forecast analysis
- **SQL Query Generation**: Parameterized queries against star schema
- **Result Caching**: Redis-based caching (optional)
- **Privacy Enforcement**: Customer ID anonymization (C-XXXXXXXX)

### 4. Data Access Layer

**Purpose**: Database interaction and caching

**Components**:
- **Connection Pool**: PostgreSQL connection pooling (max: 30, min: 5, overflow: 10)
- **Query Layer**: Raw SQL with parameterization (no ORM overhead)
- **Redis Cache** (Optional):
  - Customer profile caching (TTL: 5 minutes)
  - Churn prediction caching (TTL: 1 hour)
  - 10-20x performance improvement

**Connection String**:
```python
# Format: postgresql://user:pass@host:port/database?sslmode=require
DATABASE_URL = os.getenv("DATABASE_URL")
```

### 5. Data Layer

**Purpose**: Persistent data storage

**Schema Design**: Star schema optimized for analytical queries

**Core Tables**:
- `fact_customer_current`: Customer-level metrics (27K rows)
- `combined_sales`: Transaction history (1.2M rows)
- `customer_profiles`: Feature vectors for segmentation (27K rows)
- `archetypes`: Behavioral cohort definitions (868 rows)

**Indexes**: Optimized for customer_id and date-based queries

---

## Data Architecture

### Star Schema Design

```
┌───────────────────────────────────────────────────────────────┐
│                   Fact Table: combined_sales                   │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  • order_id (PK)          • customer_id (FK)             │ │
│  │  • order_date             • order_value                  │ │
│  │  • product_category       • shipping_cost                │ │
│  │  • discount_amount        • tax_amount                   │ │
│  │  • payment_method         • fulfillment_status           │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────┬───────────────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
┌─────────────────┐ ┌──────────────┐ ┌────────────────────┐
│  Dimension:     │ │ Dimension:   │ │  Dimension:        │
│  fact_customer  │ │  customer_   │ │  archetypes        │
│  _current       │ │  profiles    │ │                    │
│                 │ │              │ │                    │
│  • customer_id  │ │• customer_id │ │ • archetype_id     │
│  • ltv          │ │• features[8] │ │ • segments[8]      │
│  • total_orders │ │• cluster_id  │ │ • member_count     │
│  • avg_order    │ │• created_at  │ │ • avg_ltv          │
│  • churn_risk   │ │              │ │ • traits[]         │
│  • days_since   │ │              │ │                    │
└─────────────────┘ └──────────────┘ └────────────────────┘
```

### Data Flow

```
1. Source Data (Azure SQL)
   │
   ▼
2. Daily Sync Script
   │
   ├──> combined_sales table (append new orders)
   ├──> fact_customer_current (upsert metrics)
   └──> customer_profiles (recompute features)
   │
   ▼
3. Clustering Algorithm
   │
   └──> archetypes table (868 cohorts)
   │
   ▼
4. Query Layer (MCP Tools)
   │
   └──> REST API responses
   │
   ▼
5. AI Response Generation
   │
   └──> Gorgias/Slack formatted responses
```

### Data Retention

- **Transaction Data**: Indefinite retention
- **Customer Metrics**: Updated daily, historical snapshots stored
- **Analytics Cache**: 5 minutes (profiles), 1 hour (predictions)
- **Logs**: 7 days (Railway default)

---

## Application Architecture

### Component Diagram

```
backend/
├── main.py                      # FastAPI app initialization
├── api/
│   ├── routers/
│   │   ├── webhooks.py          # Gorgias/Slack webhook handlers
│   │   ├── analytics.py         # Analytics endpoints
│   │   ├── mcp.py               # MCP tool endpoints
│   │   ├── admin.py             # Admin endpoints
│   │   ├── customers.py         # Customer endpoints
│   │   └── campaigns.py         # Campaign endpoints
│   ├── auth.py                  # API key verification
│   └── dependencies.py          # FastAPI dependencies
├── middleware/
│   ├── logging_config.py        # Structured logging setup
│   ├── error_handling.py        # Error handlers
│   └── metrics.py               # Prometheus metrics (optional)
├── cache/
│   └── redis_cache.py           # Redis caching layer (optional)
└── integrations/
    ├── gorgias_ai_assistant.py  # Gorgias AI integration
    ├── ticketing/
    │   └── gorgias.py           # Gorgias API client
    └── slack_bot.py             # Slack bot logic

mcp_server/
└── segmentation_server.py       # MCP analytics tools

scripts/
├── combine_and_upload_csv.py    # Data sync script
└── load_linda_data.py           # Database initialization
```

### Request Flow

#### Example: Gorgias Webhook Processing

```
1. Gorgias → POST /api/gorgias/webhook
   │
   ├──> Verify HMAC-SHA256 signature
   ├──> Extract correlation ID
   ├──> Log request received
   │
2. GorgiasAIAssistant.handle_ticket_webhook()
   │
   ├──> Detect source (RingCentral/SMS/email/chat)
   ├──> Check automation filters (tags, status, via field)
   ├──> Extract customer message (skip from_agent=true)
   ├──> Extract customer ID (external_id, meta, id, email)
   │
3. Fetch customer analytics
   │
   ├──> GET /api/mcp/customer/{customer_id}
   ├──> GET /api/mcp/customer/{customer_id}/churn-risk
   ├──> Cache hit/miss (Redis if enabled)
   │
4. Generate AI response
   │
   ├──> Build source-specific prompt
   ├──> Call Claude 3.5 Haiku API
   ├──> Parse response (customer message + agent recommendation)
   │
5. Post internal note
   │
   ├──> Format analytics summary (source, LTV, churn, orders)
   ├──> POST to Gorgias /api/tickets/{id}/messages
   ├──> Log success/failure
   │
6. Return response
   │
   └──> {"status": "success", "ticket_id": "...", "draft_posted": {...}}
```

---

## Integration Architecture

### Gorgias Integration

**Webhook Configuration**:
- **URL**: `https://ecommerce-backend-staging-a14c.up.railway.app/api/gorgias/webhook`
- **Secret**: SHA-256 HMAC signature verification
- **Events**: Ticket message created
- **Rate Limit**: 1000/hour

**Metadata Usage**:
| Field | Purpose |
|-------|---------|
| `via` | Source detection (email, sms, chat, voice, api) |
| `channel` | Channel type (email, sms, chat, voice) |
| `status` | Filter closed/spam tickets |
| `tags` | Manual override (`ai_ignore`, `force-ai`) |
| `from_agent` | Skip outgoing messages (true = FROM us) |
| `created_by_agent` | Allow agent-forwarded tickets |
| `subject` | Contextual clues (RingCentral, SMS) |
| `customer.email` | Service identifiers |

**Source-Specific Handling**:
| Source | Response Style | Max Length |
|--------|---------------|------------|
| SMS | Extra concise, casual | 2-3 sentences |
| Chat | Quick, conversational | 2-3 sentences |
| Email | Standard professional | 4-6 sentences |
| RingCentral | Mention voicemail/callback | 4-6 sentences |
| Phone | Acknowledge verbal explanation | 4-6 sentences |

### Slack Integration

**Event Types**:
- `app_mention`: @mentions in channels
- `message.im`: Direct messages to bot
- `app_home_opened`: Home tab opened

**Slash Commands**:
- `/churn-check <customer_id>`: Check churn risk
- `/segment-info <archetype_id>`: Get segment details
- `/forecast <metric> <period>`: Get forecast

**Response Format**: Block Kit with formatted tables and charts

### Anthropic Claude Integration

**Model**: claude-3-5-haiku-20241022

**Usage Patterns**:

1. **Natural Language Routing**
   - **Input**: User query string
   - **Output**: Function call with tool name and parameters
   - **Max Tokens**: 1024
   - **Temperature**: 0.7

2. **Gorgias Response Generation**
   - **Input**: Customer message + analytics context + source
   - **Output**: Draft response + agent recommendation
   - **Max Tokens**: 600
   - **Temperature**: 0.7

**Cost Optimization**:
- Haiku model: $0.25/1M input tokens, $1.25/1M output tokens
- Average ticket: ~800 input tokens, ~200 output tokens
- Cost per ticket: ~$0.0004 ($0.40 per 1000 tickets)

---

## Infrastructure Architecture

### Deployment Environment

**Platform**: Railway (Cloud PaaS)

**Components**:
- **Application Service**: FastAPI app (Python 3.11)
- **Database Service**: PostgreSQL 15
- **Redis Service** (Optional): Redis 7
- **Build**: Docker-based (Nixpacks auto-detection)

### Resource Allocation

**Application**:
- **CPU**: Shared vCPU
- **Memory**: 512 MB minimum, 2 GB maximum
- **Storage**: Ephemeral (logs only)
- **Networking**: HTTPS with automatic SSL

**Database**:
- **CPU**: Shared vCPU
- **Memory**: 1 GB
- **Storage**: 5 GB SSD
- **Connection Limit**: 100 (pool: 30)

**Redis** (Optional):
- **Memory**: 256 MB
- **Eviction Policy**: allkeys-lru
- **Persistence**: None (cache only)

### Networking

```
Internet
   │
   ▼
┌─────────────────────────────────────────┐
│  Railway Edge Network (Global CDN)      │
│  • TLS 1.3 encryption                   │
│  • Automatic SSL certificate            │
│  • DDoS protection                       │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Application Service                    │
│  ecommerce-backend-staging-a14c         │
│  • Port: 8080                           │
│  • Domain: *.up.railway.app             │
└────────┬──────────┬─────────────────────┘
         │          │
         │          └──────────────┐
         ▼                         ▼
┌──────────────────┐     ┌──────────────────┐
│  PostgreSQL      │     │  Redis (Optional)│
│  • Internal DNS  │     │  • Internal DNS  │
│  • Private net   │     │  • Private net   │
└──────────────────┘     └──────────────────┘
```

### Environment Variables

**Required**:
```bash
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
ANTHROPIC_API_KEY=sk-ant-...
ADMIN_KEY=<hex_string>  # API authentication
```

**Gorgias**:
```bash
GORGIAS_DOMAIN=lindas
GORGIAS_USERNAME=lindas.quimbiai@proton.me
GORGIAS_API_KEY=<api_key>
GORGIAS_WEBHOOK_SECRET=<hex_string>
```

**Optional**:
```bash
REDIS_URL=redis://default:password@host:port  # Caching
SLACK_BOT_TOKEN=xoxb-...                       # Slack bot
SLACK_SIGNING_SECRET=<hex_string>              # Slack webhooks
```

---

## Security Architecture

### Authentication & Authorization

**API Authentication**:
- **Method**: API key via `X-API-Key` header
- **Storage**: Environment variable (`ADMIN_KEY`)
- **Scope**: Admin endpoints only
- **Rotation**: Manual (no automated rotation)

**Webhook Verification**:
- **Gorgias**: HMAC-SHA256 signature verification
- **Slack**: Request signature validation
- **Anthropic**: API key in Authorization header

### Data Privacy

**Customer Data Anonymization**:
- Customer IDs exposed as `C-XXXXXXXX` format
- No PII (names, addresses, emails) in API responses
- Aggregate metrics only (no individual counts below threshold)

**Sensitive Data Handling**:
- No credit card data stored
- No password storage (external auth only)
- Logs sanitized (no sensitive fields)

### Network Security

**Transport Layer**:
- **HTTPS Only**: TLS 1.3 encryption
- **Certificate**: Automatic Let's Encrypt
- **HSTS**: Strict Transport Security enabled

**Application Layer**:
- **Rate Limiting**: Per-IP, per-endpoint limits
- **Input Validation**: Pydantic models
- **SQL Injection Prevention**: Parameterized queries
- **XSS Prevention**: Content-Type headers, no user HTML

### Secrets Management

**Storage**: Railway environment variables (encrypted at rest)

**Access Control**:
- Secrets never logged
- Secrets never exposed in responses
- Secrets rotated manually (no automated rotation)

---

## Performance & Scalability

### Performance Metrics

**Target SLAs**:
| Endpoint Type | P50 | P95 | P99 |
|--------------|-----|-----|-----|
| Health Check | <50ms | <100ms | <200ms |
| Random Customer | <100ms | <200ms | <500ms |
| Analytics Query | <300ms | <1s | <3s |
| AI Response (Gorgias) | <5s | <10s | <15s |

**Actual Performance** (without caching):
- Random customer: ~100ms
- Churn prediction: ~200ms
- Segment analysis: ~500ms
- AI response: ~3-8s (depends on Claude API)

**With Redis Caching**:
- Customer profile: 10-20ms (10x improvement)
- Churn prediction: 50-100ms (5x improvement)
- Cache hit rate: ~70-80%

### Scalability Considerations

**Current Limits**:
- **Database**: 100 connections, 30 in pool
- **Request Rate**: 1000/hour per endpoint
- **Concurrent Requests**: ~50 (limited by connection pool)
- **Data Volume**: 1.2M transactions, 27K customers

**Scaling Strategy**:

**Vertical Scaling** (Current):
- Increase Railway service resources (memory, CPU)
- Increase database connection pool
- Add Redis for caching

**Horizontal Scaling** (Future - Multi-Tenant):
- Multiple app instances behind load balancer
- Read replicas for database
- Redis cluster for cache
- Tenant-based data partitioning

### Optimization Techniques

**Database**:
- Indexed customer_id, order_date columns
- Materialized views for aggregate queries
- Connection pooling (min: 5, max: 30, overflow: 10)

**Caching**:
- Redis cache for customer profiles (TTL: 5 min)
- Redis cache for churn predictions (TTL: 1 hour)
- In-memory cache for archetype definitions

**Application**:
- Async I/O throughout (FastAPI, HTTPX)
- Batch database queries where possible
- Lazy loading of large result sets

---

## Observability & Monitoring

### Logging

**Format**: Structured JSON logging (production)

**Fields**:
- `timestamp`: ISO 8601 timestamp
- `level`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `message`: Log message
- `correlation_id`: Request tracking ID
- `service`: Service name
- `module`: Python module
- `function`: Function name
- `extra`: Additional context (dict)

**Example**:
```json
{
  "timestamp": "2025-11-04T22:15:30.123Z",
  "level": "INFO",
  "message": "Processing Gorgias ticket",
  "correlation_id": "abc123...",
  "service": "ecommerce-backend",
  "module": "gorgias_ai_assistant",
  "extra": {
    "ticket_id": "235000484",
    "source": "ringcentral",
    "customer_id": "7843694739711"
  }
}
```

### Metrics (Optional - Prometheus)

**Application Metrics**:
- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: Request duration histogram
- `http_requests_in_progress`: Active requests gauge
- `database_connections_total`: Database connection pool metrics
- `cache_hits_total`: Cache hit rate counter

**Business Metrics**:
- `tickets_processed_total`: Gorgias tickets processed
- `ai_responses_generated_total`: AI responses generated
- `customer_queries_total`: Natural language queries processed

### Health Checks

**Endpoint**: `GET /health`

**Checks**:
- API service health
- MCP server health
- Database connectivity
- Data availability (customer count)

**Response**:
```json
{
  "status": "healthy",
  "components": {
    "api": "healthy",
    "mcp_server": "healthy",
    "database": "healthy"
  },
  "data_status": {
    "customers_loaded": 27415,
    "archetypes_available": 868
  }
}
```

### Error Tracking

**Error Handling**:
- Correlation ID in all error responses
- Error sanitization (no sensitive data)
- Automatic retry for transient failures (Claude API)

**Error Logging**:
- Full exception stack traces logged
- Correlation ID for request tracing
- Contextual data (customer_id, ticket_id, etc.)

---

## Deployment Architecture

### CI/CD Pipeline

**Repository**: GitHub (Quimbi-ai/Ecommerce-backend)

**Deployment Flow**:
```
1. Developer pushes to main branch
   │
   ▼
2. GitHub triggers Railway webhook
   │
   ▼
3. Railway builds Docker image (Nixpacks)
   │
   ├──> Install dependencies (requirements.txt)
   ├──> Copy source code
   └──> Set entrypoint: uvicorn backend.main:app
   │
   ▼
4. Railway deploys new image
   │
   ├──> Health check: GET /health
   ├──> Readiness check: 200 OK
   └──> Traffic cutover (zero-downtime)
   │
   ▼
5. New version live
   │
   └──> Old container terminated after 60s
```

**Rollback**: Manual via Railway UI or `git revert + push`

### Environment Management

**Environments**:
- **Staging**: `ecommerce-backend-staging-a14c.up.railway.app`
- **Production**: Not yet deployed (pending multi-tenant work)

**Configuration Management**:
- Environment-specific variables in Railway
- Secrets stored in Railway (encrypted)
- No secrets in code/git

### Database Migrations

**Strategy**: Manual SQL migrations (no ORM)

**Process**:
1. Write SQL migration script
2. Test on staging database
3. Apply to production during maintenance window
4. Verify with health check

**Backup Strategy**:
- Railway automatic daily backups (7 days retention)
- Manual snapshot before major migrations

---

## Future Architecture

### Multi-Tenant Architecture (Next Phase)

**Goal**: Support multiple e-commerce clients on single deployment

**Required Changes**:

#### 1. Data Layer
```sql
-- Add tenant table
CREATE TABLE tenants (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  subdomain VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Add tenant_id to all tables
ALTER TABLE combined_sales ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE fact_customer_current ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE customer_profiles ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE archetypes ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);

-- Add tenant-aware indexes
CREATE INDEX idx_sales_tenant_customer ON combined_sales(tenant_id, customer_id);
CREATE INDEX idx_customers_tenant ON fact_customer_current(tenant_id);
```

#### 2. Application Layer
- **Tenant Context Middleware**: Extract tenant from subdomain/header
- **Tenant-Scoped Queries**: Add `WHERE tenant_id = ?` to all queries
- **Tenant-Specific Configuration**: Per-tenant Gorgias/Slack credentials
- **Data Isolation**: Ensure no cross-tenant data leakage

#### 3. API Changes
- **Tenant Identification**: Subdomain (`lindas.api.quimbi.com`) or `X-Tenant-ID` header
- **Tenant Management**: Admin endpoints for tenant CRUD
- **Billing Integration**: Usage tracking per tenant

#### 4. Infrastructure
- **Horizontal Scaling**: Multiple app instances with load balancer
- **Database Partitioning**: Partition tables by tenant_id
- **Separate Databases** (Optional): One database per tenant for large clients

### Estimated Timeline

**Phase 1: Linda's Staging Completion** (Current)
- ✅ Single-tenant production deployment
- ✅ Gorgias AI integration stable
- ✅ Source detection and filtering complete
- ⏳ ShipStation integration (pending API credentials)
- ⏳ Production testing and refinement

**Phase 2: Multi-Tenant Preparation** (After Linda's complete)
- Database schema changes (tenant_id columns)
- Tenant context middleware
- Tenant management endpoints
- Data migration strategy

**Phase 3: Multi-Tenant Deployment**
- Second client onboarding
- Load testing with multiple tenants
- Monitoring per-tenant metrics
- Billing integration

**Phase 4: Scale & Optimize**
- Horizontal scaling (multiple instances)
- Database read replicas
- Global CDN for edge caching
- Advanced monitoring and alerting

---

## Appendix

### Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Language** | Python | 3.11 |
| **Web Framework** | FastAPI | 0.104+ |
| **ASGI Server** | Uvicorn | 0.24+ |
| **Database** | PostgreSQL | 15 |
| **Cache** | Redis | 7 (optional) |
| **AI** | Anthropic Claude | 3.5 Haiku |
| **HTTP Client** | HTTPX | 0.25+ |
| **Logging** | Python logging + JSON | stdlib |
| **Metrics** | Prometheus | 0.19+ (optional) |
| **Hosting** | Railway | - |

### Repository Structure

```
unified-segmentation-ecommerce/
├── backend/                 # FastAPI application
│   ├── main.py             # App entry point
│   ├── api/                # API routers
│   ├── middleware/         # Middleware components
│   ├── cache/              # Caching layer
│   └── integrations/       # External integrations
├── mcp_server/             # MCP analytics tools
├── frontend/               # Chat UI (single-page)
├── scripts/                # Data sync scripts
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md     # This document
│   ├── AI_ML_INTEGRATION.md
│   └── PRODUCT_REQUIREMENTS.md
└── requirements.txt        # Python dependencies
```

### Glossary

- **MCP**: Model Context Protocol - Tool-based AI interaction pattern
- **LTV**: Lifetime Value - Total revenue from a customer
- **Churn**: Customer attrition - likelihood of stopping purchases
- **Archetype**: Behavioral cohort - group of similar customers
- **Star Schema**: Data warehouse design pattern
- **HMAC**: Hash-based Message Authentication Code
- **Correlation ID**: Unique request identifier for tracing

---

**Document Version**: 2.0
**Author**: Quimbi AI Engineering Team
**Review Cycle**: Quarterly
**Next Review**: February 2026
