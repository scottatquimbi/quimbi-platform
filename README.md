# Unified Segmentation E-commerce

**AI-Powered Customer Intelligence for Support & Marketing**

An enterprise-grade platform combining Shopify order data with Quimbi behavioral segmentation to deliver personalized customer support and predictive analytics.

---

## What is This?

**For Support Agents:** Get AI-generated support responses with complete customer context (purchase history, behavioral profile, churn risk)

**For Developers:** REST API for customer data, behavioral insights, and predictive analytics

**For Operations:** Monitor system health, manage data sync, respond to incidents

---

## Quick Links

**Getting Started:**
- [Your First 15 Minutes](GETTING_STARTED.md) - Onboarding guide for all user types
- [Architecture Overview](ARCHITECTURE.md) - System design and components
- [API Documentation](docs/API_DOCUMENTATION.md) - Full API reference
- [Security Policy](SECURITY.md) - Security architecture and compliance

**Operations:**
- [Deployment Guide](operations/DEPLOYMENT.md) - Deploy to Railway
- [Monitoring Setup](operations/MONITORING.md) - Observability and alerting
- [Incident Runbook](operations/INCIDENT_RUNBOOK.md) - Emergency response procedures
- [Sync Troubleshooting](operations/SYNC_TROUBLESHOOTING.md) - Data sync issues

**Reference:**
- [Supported Queries](docs/SUPPORTED_QUERIES.md) - All available API queries
- [Behavioral Segmentation](docs/BEHAVIORAL_SEGMENTATION.md) - Quimbi features explained
- [Redis Caching](reference/REDIS_CACHING.md) - Performance optimization
- [Changelog](CHANGELOG.md) - Version history

---

## Key Features

**Data Integration:**
- ✅ Shopify API integration (real-time orders, tracking, customer data)
- ✅ Quimbi behavioral segmentation (27,415 customers, 868 archetypes)
- ✅ Gorgias webhook integration (AI-generated support responses)
- ✅ Hybrid data lookup with graceful fallbacks

**Predictive Analytics:**
- ✅ Churn risk prediction (0-100% risk score per customer)
- ✅ Customer lifetime value analysis
- ✅ Behavioral archetype segmentation
- ✅ Growth forecasting (6/12/18/24 months)

**AI-Powered Support:**
- ✅ Personalized response generation using Claude AI
- ✅ Real-time customer context (orders, tracking, LTV)
- ✅ Retention strategy recommendations
- ✅ High-value customer identification

**Enterprise Features:**
- ✅ Production-grade observability (structured logging, correlation IDs)
- ✅ Redis caching (10-20x faster responses)
- ✅ Database connection pooling (30 max connections)
- ✅ API authentication (API key-based)
- ✅ Security & compliance (GDPR/CCPA)

---

## 📊 Platform Overview

| Component | Description |
|-----------|-------------|
| **Backend API** | FastAPI with 10+ analytics endpoints |
| **Database** | PostgreSQL star schema (Railway) |
| **Data Sync** | Automated Azure SQL → Postgres daily sync |
| **Frontend** | Single-page chat interface |
| **Archetypes** | 868 behavioral cohorts |
| **Behavioral Axes** | 8 (frequency, value, category, sensitivity, cadence, maturity, repurchase, returns) |
| **Response Time** | <300ms for most queries |
| **Privacy** | Full anonymization - no customer counts exposed |

---

## 🚀 Quick Start

### Try the Live Demo

1. Open `frontend/index.html` in your browser
2. Try these natural language queries (powered by Claude AI):
   ```
   "show me a random customer"
   "how many people will be engaged during halloween"
   "what's our revenue forecast for Q4"
   "whos gonna churn next month"
   "which customers should I target for Black Friday"
   "what are the top archetypes for money"
   ```

   **Note:** Natural language routing uses Claude 3.5 Haiku for intent understanding.
   No keyword matching - works with any phrasing!

### Development Setup

```bash
# 1. Clone repository
git clone https://github.com/Quimbi-ai/Ecommerce-backend.git
cd Ecommerce-backend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set database URL (optional - runs in-memory if not set)
export DATABASE_URL="postgresql://..."

# 4. Start API server
cd backend
uvicorn main:app --reload --port 8080

# 5. Open frontend
open ../frontend/index.html
```

---

## 🎨 Chat Interface

### Example Queries

**Customer Analysis:**
```
You: "show me a random customer"
AI:  Customer Profile
     🔑 Customer ID: C-5A3B2F18
     💰 Lifetime Value: $523,710
     📦 Total Orders: 1,817
     🎯 Archetype: arch_880996

     Behavioral Traits:
     • purchase_value:premium
     • purchase_frequency:power_buyer
     • category_affinity:multi_category
```

**Growth Projection:**
```
You: "how many users will we have next year"
AI:  📊 Customer Growth Projection
     📅 Timeframe: 12 months
     📈 Projected Growth Rate: +21.36%

     Assumptions:
     ⚠️ Monthly Churn Rate: 0%
     👤 Avg Customer Tenure: 717 days
```

**Archetype Analysis:**
```
You: "break the customer growth by archetype"
AI:  📊 Archetype Growth Projection (12 months)

     #1: arch_650665 📈
     💰 Total LTV: $1,316,563
     📊 Growth Rate: +20.64%
     🎯 Relative Size: 100% (vs largest segment)
     ⚠️ Churn Rate: 0.0%/mo
```

---

## 📡 API Endpoints

### Core Analytics

**GET /health**
- System status and data availability
- Returns: API health, archetype count, data source

**GET /api/mcp/customer/random**
- Get random customer profile
- Returns: Anonymized ID, LTV, orders, archetype, traits

**GET /api/mcp/customer/{id}**
- Get specific customer profile
- Returns: Full behavioral profile with segments

**GET /api/mcp/customer/{id}/churn-risk**
- Predict churn risk for customer
- Returns: Risk level (high/medium/low), score, recommendations

### Aggregate Analytics

**GET /api/mcp/churn/aggregate**
- Aggregate churn risk analysis
- Returns: Risk distribution percentages, 30/90-day estimates
- Sample: 1,000 customers

**GET /api/mcp/growth/projection?months=12**
- Customer base growth projection
- Params: `months` (6/12/18/24)
- Returns: Growth rate %, churn rate, assumptions

**GET /api/mcp/archetypes/top?metric=total_ltv&limit=10**
- Top archetypes ranking
- Params: `metric` (total_ltv, avg_ltv, member_count), `limit`
- Returns: Top N archetypes with metrics

**GET /api/mcp/archetypes/growth-projection?months=12&top_n=10**
- Archetype-segmented growth projection
- Params: `months`, `top_n`
- Returns: Per-archetype growth rates, churn, LTV

### MCP Tools (for AI Agents)

**GET /api/mcp/tools**
- List available MCP tools
- Returns: 6 tools for customer behavioral queries

**POST /api/mcp/query**
- Execute MCP tool query
- Body: `{"tool": "get_customer_profile", "params": {"customer_id": "..."}}`

---

## 🗄️ Database Schema

### Star Schema Design

**Dimension Tables:**
- `dim_archetype_l1` - Level 1 archetypes (dominant-only)
- `dim_archetype_l2` - Level 2 archetypes (with strength binning)
- `dim_archetype_l3` - Level 3 archetypes (fuzzy top-2)

**Fact Tables:**
- `fact_customer_current` - Current customer state
- `fact_customer_history` - Historical snapshots (7/14/28 day tracking)

**Columns:**
```sql
fact_customer_current (
    customer_id TEXT PRIMARY KEY,
    archetype_level2_id TEXT,
    lifetime_value NUMERIC,
    total_orders INTEGER,
    days_since_last_purchase INTEGER,
    customer_tenure_days INTEGER,
    dominant_segments JSONB,
    membership_strengths JSONB,
    snapshot_date DATE
)
```

---

## 🔮 Predictive Features

### 1. Churn Prediction

**Individual Level:**
- Analyzes: Recency, frequency, value trends
- Returns: High/Medium/Low risk + confidence score
- Use case: Identify at-risk customers for retention campaigns

**Aggregate Level:**
- Sample size: 1,000 customers
- Extrapolates to full population
- Returns: Risk distribution percentages

### 2. Growth Forecasting

**Customer Base:**
- Historical acquisition rate from tenure data
- Churn rate from risk analysis
- Month-by-month projections

**By Archetype:**
- Archetype-specific churn rates
- Proportional acquisition modeling
- Growth/shrink identification per segment

### 3. Value Prediction

**Top Archetypes:**
- Ranked by total LTV, avg LTV, or member count
- Shows population percentages
- Includes behavioral segment profiles

---

## 🔐 Privacy & Anonymization

### What's Anonymized

✅ **Customer IDs** - Hashed to C-XXXXXXXX format
✅ **Customer Counts** - Not shown in most displays
✅ **Business Name** - Generic "Customer Intelligence Platform"
✅ **Absolute Metrics** - Replaced with percentages/ratios

### What's Preserved

✅ **Growth Rates** - Percentage changes
✅ **Churn Risks** - Percentage distributions
✅ **LTV Metrics** - Dollar values
✅ **Behavioral Segments** - Archetype profiles
✅ **Relative Sizes** - Segment comparisons

### Anonymization Strategy

- **Customer IDs**: Consistent hashing (SHA-256 derived)
- **Counts**: Show percentages, not absolute numbers
- **Metrics**: Focus on rates of change, not totals
- **Segments**: Show behavioral patterns, not identities

---

## 📈 Supported Queries

### Currently Implemented (20+)

See [SUPPORTED_QUERIES.md](SUPPORTED_QUERIES.md) for comprehensive list.

**Customer Analysis:**
- "show me a random customer"
- "get a random customer profile"

**Churn Prediction:**
- "how many people will churn in the next month"
- "what percentage will churn"
- "check churn risk" (after viewing customer)

**Growth Projections:**
- "how many users will we have next year"
- "project customer growth over 6 months"

**Archetype Analysis:**
- "what are the top archetypes for money"
- "which archetypes are growing"
- "break the customer growth by archetype"

### Future Queries (150+)

Documented in [SUPPORTED_QUERIES.md](SUPPORTED_QUERIES.md):
- Customer LTV predictions
- Next purchase date forecasting
- Campaign targeting optimization
- What-if scenarios
- Anomaly detection
- And much more...

---

## 🏗️ Architecture

### Backend (FastAPI)
```
backend/
├── main.py                 # API server with 10+ endpoints
├── core/
│   ├── archetype_analyzer.py
│   ├── discovery.py
│   └── clustering.py
├── loaders/
│   └── star_schema_loader.py
└── mcp_server/
    └── segmentation_server.py
```

### Frontend (Single-Page App)
```
frontend/
└── index.html             # Chat interface with pattern matching
```

### Database (PostgreSQL)
```
Deployed on Railway
- 5 tables (3 dimension, 2 fact)
- Star schema design
- JSONB for flexible attributes
```

---

## 🚀 Deployment

### Railway (Current Production)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Link to project
railway link

# Deploy
railway up

# Check logs
railway logs
```

**Live URL:** https://ecommerce-backend-staging-a14c.up.railway.app

### Environment Variables

**Core Platform:**
```bash
DATABASE_URL=postgresql://...
PORT=8080
ANTHROPIC_API_KEY=sk-ant-api03-...  # Required for NL queries & Gorgias AI
```

**Admin API (Optional):**
```bash
ADMIN_KEY=your-secret-admin-key     # For admin endpoint access
```

**Redis Caching (Optional - NEW):**
```bash
ENABLE_CACHE=true                    # Enable Redis caching (default: true)
REDIS_URL=redis://localhost:6379/0   # Redis connection URL
CACHE_TTL=3600                       # Default cache TTL in seconds (default: 1 hour)
```

**Observability (Optional - NEW):**
```bash
ENABLE_PROMETHEUS_METRICS=false      # Enable Prometheus metrics endpoint (default: false)
LOG_LEVEL=INFO                       # Logging level (default: INFO)
JSON_LOGS=false                      # Use JSON log format (default: false, auto-enabled in Railway)
```

**Database Pooling (Optional - NEW):**
```bash
DB_POOL_SIZE=20                      # Connection pool size (default: 20 prod, 5 dev)
DB_MAX_OVERFLOW=10                   # Max overflow connections (default: 10 prod, 5 dev)
DB_POOL_TIMEOUT=30                   # Pool timeout in seconds (default: 30)
DB_POOL_RECYCLE=1800                 # Recycle connections after seconds (default: 1800)
DB_POOL_PRE_PING=true                # Test connections before use (default: true)
```

**Gorgias AI Assistant (Optional):**
```bash
GORGIAS_DOMAIN=yourcompany           # Your Gorgias subdomain
GORGIAS_USERNAME=you@company.com     # Gorgias account email
GORGIAS_API_KEY=<base64-key>         # From Gorgias Settings → REST API
```

**Note:** `ANTHROPIC_API_KEY` is required for natural language queries and Gorgias AI responses. Get your API key from: https://console.anthropic.com/settings/keys

**Setup Guides:**
- **Redis Caching:** See [Redis Caching Guide](REDIS_CACHING_GUIDE.md) for complete setup instructions
- **Database Pooling:** See [Database Pooling Guide](DATABASE_POOLING_GUIDE.md) for optimization details
- **Gorgias Integration:** See [Integration Guide](docs/INTEGRATION_GUIDE.md) for step-by-step instructions

---

## 🧪 Testing

### Quick Test (In-Memory)
```bash
python scripts/quick_test_mcp.py
```

### Full Test (With Database)
```bash
export DATABASE_URL="postgresql://..."
python scripts/test_star_schema.py
```

### API Test
```bash
# Health check
curl https://ecommerce-backend-staging-a14c.up.railway.app/health

# Random customer
curl https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/random

# Growth projection
curl "https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/growth/projection?months=12"
```

---

## 📚 Documentation

**Start Here:**
- [GETTING_STARTED.md](GETTING_STARTED.md) - Your first 15 minutes
- [README.md](README.md) - This file - overview and navigation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design and technical overview
- [SECURITY.md](SECURITY.md) - Security architecture and compliance

**User Guides:**
- [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) - Complete API reference
- [docs/SUPPORTED_QUERIES.md](docs/SUPPORTED_QUERIES.md) - All available queries
- [docs/BEHAVIORAL_SEGMENTATION.md](docs/BEHAVIORAL_SEGMENTATION.md) - Quimbi features explained
- [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) - API authentication setup

**Operations:**
- [operations/DEPLOYMENT.md](operations/DEPLOYMENT.md) - Deployment procedures
- [operations/MONITORING.md](operations/MONITORING.md) - Monitoring and alerting
- [operations/INCIDENT_RUNBOOK.md](operations/INCIDENT_RUNBOOK.md) - Incident response
- [operations/SYNC_GUIDE.md](operations/SYNC_GUIDE.md) - Data sync procedures
- [operations/SYNC_TROUBLESHOOTING.md](operations/SYNC_TROUBLESHOOTING.md) - Sync issues

**Technical Reference:**
- [reference/REDIS_CACHING.md](reference/REDIS_CACHING.md) - Caching strategy and setup
- [reference/DATABASE_POOLING.md](reference/DATABASE_POOLING.md) - Database optimization
- [reference/STRUCTURED_LOGGING.md](reference/STRUCTURED_LOGGING.md) - Logging standards

**Other:**
- [CHANGELOG.md](CHANGELOG.md) - Version history and migration notes

---

## 🤖 Gorgias AI Assistant

**NEW:** Automatically generate personalized customer support responses using customer analytics.

### What It Does

When a customer sends a support ticket:
1. System fetches their purchase history, LTV, churn risk, and behavioral patterns
2. Claude AI generates a personalized draft response
3. Draft appears as internal note in Gorgias for CS agent to review/edit
4. Agent sends response (with full control)

### Example

**Customer:** "My order hasn't arrived yet!"

**AI Generates:**
```
📊 CUSTOMER INSIGHTS (Internal)
💰 Lifetime Value: $8,450 (VIP)
⚠️  Churn Risk: 78% (CRITICAL)
🎯 Frequent buyer, shops every 30 days

⚠️ RETENTION PRIORITY: High-value at churn risk!

━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hi Sarah,

I'm so sorry to hear your order hasn't arrived yet!
As one of our most valued customers, I want to make
this right immediately.

[Personalized response with retention strategy]
```

### Setup

See: [Integration Guide](docs/INTEGRATION_GUIDE.md) (30 minutes, no coding required)

**Benefits:**
- ✅ Faster response times
- ✅ Personalized based on customer value
- ✅ Smart retention strategies (VIP vs new customer)
- ✅ Cost: ~$0.0001 per ticket
- ✅ Agent maintains full control

---

## 🔄 Recent Updates

### v1.2.0 (2025-10-22)

**New Features:**
- ✅ Combined Sales Data - 1.2M rows uploaded to Railway Postgres
- ✅ CSV-based data pipeline (product_sales_order.csv + sales_data_orders.csv)
- ✅ Combined sales table with 26 columns (products, orders, location, status)
- ✅ Date range: 2021-01-26 to 2025-10-22 (4+ years of data)
- ✅ Geographic coverage: 1,044,911 rows with location data (85.5%)
- ✅ Performance indexes created for fast querying
- ✅ Admin API endpoints for data sync management

**Data Loaded:**
- 1,221,736 total line items
- 200,729 unique orders
- 93,564 unique customers
- 22,318 unique products
- Complete fulfillment status tracking

### v1.1.0 (2025-10-17)

**New Features:**
- ✅ Gorgias AI Assistant - Auto-generated personalized support responses
- ✅ Customer analytics enrichment (LTV, churn, patterns)
- ✅ Retention strategy recommendations
- ✅ Behavioral pattern insights (without archetype names)
- ✅ Multi-provider ticketing (Zendesk + Gorgias)
- ✅ Complete documentation for non-technical teams

### v1.0.0 (2025-10-16)

**New Features:**
- ✅ Archetype-segmented growth projections
- ✅ Aggregate churn risk analysis
- ✅ Top archetypes ranking (3 metrics)
- ✅ Random customer endpoint
- ✅ Complete anonymization
- ✅ Natural language query interface

**Privacy Enhancements:**
- Removed all customer counts from displays
- Anonymized customer IDs with hashing
- Replaced absolutes with percentages
- Generic branding

**Performance:**
- <300ms response times
- 1,000 customer sampling for aggregates
- Efficient star schema queries

---

## 🛠️ Technology Stack

- **Backend:** FastAPI, Python 3.11-3.13
- **Database:** PostgreSQL (Railway)
- **Frontend:** HTML/CSS/JavaScript (vanilla)
- **ML:** scikit-learn (fuzzy c-means clustering)
- **AI:** Anthropic Claude (function calling), OpenAI, Google Gemini
- **Deployment:** Railway
- **Analytics:** Custom behavioral segmentation engine

---

## 📊 Data Pipeline

1. **Discovery** - Analyze customer behavioral data
2. **Clustering** - Fuzzy c-means on 8 axes
3. **Archetype Creation** - Generate L1/L2/L3 cohorts
4. **Star Schema Upload** - PostgreSQL storage
5. **API Serving** - FastAPI with MCP tools
6. **Frontend** - Chat interface for queries

---

## 🤝 Contributing

This is a private project. For questions or suggestions:
- Create an issue in the GitHub repo
- Contact: scott@quimbi.ai

---

## 📄 License

Proprietary - All rights reserved

---

## 🎯 Use Cases

### 1. Customer Service
- Instant customer behavioral context
- Pre-written response scripts
- VIP identification

### 2. Marketing
- Segment-specific campaigns
- Churn prevention targeting
- Growth opportunity identification

### 3. Analytics
- Growth forecasting
- Segment performance tracking
- Trend identification

### 4. Strategy
- What-if scenario planning
- Cohort analysis
- Revenue projections

---

## 📞 Support

For technical support or questions:
- **Email:** scott@quimbi.ai
- **GitHub Issues:** https://github.com/Quimbi-ai/Ecommerce-backend/issues
- **Documentation:** See docs/ folder

---

**Built with ❤️ by Quimbi AI**

*Last Updated: 2025-10-21*
