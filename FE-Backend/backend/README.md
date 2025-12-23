# AI-First CRM Backend

**Philosophy: Intelligence Replaces Interface**

Every dropdown removed is AI making that decision. The best AI is the AI you don't notice.

## Overview

This is the backend for an e-commerce CRM system built around invisible intelligence. Instead of complex UIs for sorting, filtering, and categorizing - the AI does it automatically.

### Core Features

#### Phase 1 (Current Implementation)

1. **Smart Inbox Ordering** ✅
   - Tickets automatically ordered by composite score
   - No sort UI needed - always intelligent order
   - Considers: churn risk, LTV, urgency, age, difficulty, sentiment
   - Scoring algorithm: `(Churn × 3.0) + (LTV/1000 × 2.0) + (Urgency × 1.5) + Age + Difficulty + Sentiment`

2. **Topic Alerts** ✅
   - Agents can specify keywords to watch for
   - Matching tickets get +5.0 score boost
   - Temporary intent-setting for emerging issues
   - Example: "chargeback,fraud,wrong address"

3. **AI Draft Generation** ✅
   - Channel-aware response generation (Email ≠ SMS ≠ Chat)
   - Automatic context gathering (orders, tracking, past tickets)
   - Personalized to customer value and churn risk
   - No template selection needed

4. **Proactive Context Gathering** ✅
   - Automatically fetches relevant orders
   - Gets tracking information
   - Retrieves past ticket patterns
   - Agent never has to search manually

#### Phase 2 (Planned)

- Auto-categorization (NLP-based tagging)
- Sentiment analysis
- Smart follow-up scheduling
- Churn prevention auto-escalation

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                     │
│  - Displays tickets in smart order                     │
│  - Shows AI drafts                                      │
│  - Minimal UI, maximum intelligence                    │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ HTTP/REST
                 ▼
┌─────────────────────────────────────────────────────────┐
│                   API Layer (FastAPI)                   │
│  - GET /api/tickets (with smart scoring)               │
│  - GET /api/ai/tickets/{id}/draft-response             │
│  - POST /api/tickets/{id}/messages                     │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Internal calls
                 ▼
┌─────────────────────────────────────────────────────────┐
│              Intelligence Layer (Services)              │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐           │
│  │ Scoring Service  │  │   AI Service     │           │
│  │ - Calc priority  │  │ - Generate draft │           │
│  │ - Rank tickets   │  │ - Context inject │           │
│  └──────────────────┘  └──────────────────┘           │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐           │
│  │ Context Service  │  │  Tag Service     │           │
│  │ - Gather orders  │  │ - Auto-tag       │           │
│  │ - Past tickets   │  │ - (Phase 2)      │           │
│  └──────────────────┘  └──────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+ (for Celery)
- Anthropic API key (or OpenAI API key)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### Configuration

Edit `.env` with your settings:

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/quimbi_crm
ANTHROPIC_API_KEY=sk-ant-...

# Optional (has defaults)
SCORING_CHURN_WEIGHT=3.0
SCORING_VALUE_WEIGHT=2.0
TOPIC_ALERT_BOOST=5.0
```

### Run Development Server

```bash
# Run FastAPI with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Tickets

#### `GET /api/tickets`

Get tickets in smart order (no sorting needed).

**Query Parameters:**
- `status` (string): Filter by status (default: "open")
- `channel` (string): Filter by channel (email, sms, chat)
- `limit` (int): Max tickets to return (default: 50)
- `page` (int): Page number (default: 1)
- `topic_alerts` (string): Comma-separated keywords to boost

**Example:**
```bash
# Get all open tickets in smart order
curl "http://localhost:8000/api/tickets?status=open"

# With topic alerts
curl "http://localhost:8000/api/tickets?topic_alerts=chargeback,fraud"
```

**Response:**
```json
{
  "tickets": [
    {
      "id": "1",
      "subject": "Order not delivered",
      "priority": "high",
      "smart_score": 12.3,
      "matches_topic_alert": false,
      "customer_id": "c1",
      "created_at": "2024-11-14T20:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 23,
    "has_next": false,
    "has_prev": false
  },
  "topic_alerts_active": [],
  "matches": 0
}
```

#### `GET /api/tickets/{ticket_id}/score-breakdown`

Debug endpoint showing why ticket has its score.

**Example:**
```bash
curl "http://localhost:8000/api/tickets/1/score-breakdown"
```

**Response:**
```json
{
  "total_score": 12.3,
  "components": {
    "churn_risk": 2.4,
    "customer_value": 7.0,
    "urgency": 1.5,
    "age": 1.0,
    "difficulty": 0.0,
    "sentiment": 2.0,
    "topic_alert": 0.0
  },
  "customer": {
    "ltv": 3500.0,
    "churn_risk": 0.8
  },
  "ticket": {
    "priority": "high",
    "age_hours": 2.3
  },
  "weights": {
    "churn_weight": 3.0,
    "value_weight": 2.0,
    "urgency_weight": 1.5,
    "topic_alert_boost": 5.0
  }
}
```

### AI

#### `GET /api/ai/tickets/{ticket_id}/draft-response`

Get AI-generated draft response.

**Example:**
```bash
curl "http://localhost:8000/api/ai/tickets/1/draft-response"
```

**Response:**
```json
{
  "content": "Hi Jane,\n\nI'm so sorry your order #54321 hasn't arrived yet...",
  "tone": "professional",
  "channel": "email",
  "reasoning": "Generated professional response for email",
  "personalization": {
    "used_order_info": true,
    "mentioned_tracking": true,
    "referenced_past_issue": false,
    "applied_vip_treatment": true
  }
}
```

## Smart Inbox Scoring Algorithm

The core of invisible intelligence is the scoring algorithm. Here's how it works:

### Components

| Component | Weight | Description | Range |
|-----------|--------|-------------|-------|
| **Churn Risk** | ×3.0 | Customer's likelihood to churn | 0-3 |
| **Customer Value** | ×2.0 | Lifetime value / $1000 | Variable |
| **Urgency** | ×1.5 | Priority level (urgent=4, high=3, normal=1, low=0.5) | 0.75-6.0 |
| **Age** | ×1.0 | 1 / hours_waiting (older = higher) | 0-1+ |
| **Difficulty** | Variable | Easy wins (+1.0), Complex issues (-1.5) | -1.5 to +1.0 |
| **Sentiment** | +2.0 | Boost for frustrated customers (sentiment < 0.3) | 0 or 2.0 |
| **Topic Alert** | +5.0 | Boost if matches agent-specified keywords | 0 or 5.0 |

### Formula

```
total_score = (churn_risk × 3.0) +
              (ltv / 1000 × 2.0) +
              (urgency × 1.5) +
              (1 / hours_waiting) +
              difficulty +
              sentiment_boost +
              topic_alert_boost
```

### Example Calculation

**Scenario:** VIP customer ($3,500 LTV) with high churn risk (0.8) submits urgent ticket about damaged product. Ticket is 2 hours old.

```
Churn:      0.8 × 3.0 = 2.4
Value:      3500 / 1000 × 2.0 = 7.0
Urgency:    4.0 × 1.5 = 6.0
Age:        1 / 2 = 0.5
Difficulty: -1.5 (complex refund issue)
Sentiment:  2.0 (customer is frustrated)
Alert:      0 (no active alerts)

Total Score: 16.4 ⭐
```

This ticket would appear at the top of the inbox.

## AI Draft Generation

### Channel-Specific Behavior

| Channel | Max Length | Tone | Special Rules |
|---------|------------|------|---------------|
| **SMS** | 160 chars | Casual | Use abbreviations, get straight to point |
| **Email** | 200 words | Professional | Proper formatting, greeting + signature |
| **Chat** | 100 words | Friendly | Short paragraphs, conversational |
| **Phone** | 75 words | Conversational | Natural speech, empathy statements |

### Automatic Context Injection

The AI automatically gathers and includes:

1. **Order Information**
   - Recent order numbers
   - Order status and tracking
   - Purchase history

2. **Customer Profile**
   - Lifetime value
   - Churn risk
   - Behavioral segments
   - VIP status

3. **Past Tickets**
   - Similar previous issues
   - Successful resolutions
   - Customer satisfaction patterns

4. **Smart Adjustments**
   - Extra care for high-value customers
   - Proactive offers for churn risk
   - Compensation suggestions when appropriate

### Example Prompt (Invisible to Agent)

```
You are a customer support agent responding to a ticket.

CHANNEL: EMAIL
- Professional but warm tone
- Can be detailed (up to 200 words)

CUSTOMER PROFILE:
- Status: ⭐ VIP CUSTOMER
- Lifetime Value: $3,500.00
- Churn Risk: 80% ⚠️ HIGH RISK
- Total Orders: 18

CUSTOMER'S MESSAGE:
"My order #54321 hasn't arrived yet..."

ISSUE CONTEXT:
- Recent Order: #54321 ($156.99)
- Order Status: in_transit
- Tracking Status: No updates for 5 days

🎯 CRITICAL INSTRUCTIONS (High-value customer at churn risk):
1. Be extra helpful and proactive
2. Offer expedited solutions
3. Consider compensation
4. Solve completely - don't ask them to do extra steps

Write the response now:
```

## Topic Alerts Feature

Topic Alerts allow agents to temporarily boost tickets matching specific keywords.

### Use Cases

1. **Fraud Wave**: Alert for "chargeback,fraud,unauthorized"
2. **Shipping Crisis**: Alert for "not delivered,tracking,delayed"
3. **Product Defect**: Alert for "broken,defective,damaged"
4. **Vendor Issue**: Alert for "supplier X,wrong item,missing parts"

### How It Works

1. Agent enters comma-separated keywords
2. System parses into list: `["chargeback", "fraud", "unauthorized"]`
3. Any ticket with matching content gets **+5.0 score boost**
4. Boosted tickets appear at top of inbox with ⚡ indicator
5. Agent handles urgent issues first
6. Alert can be cleared when crisis resolved

### API Usage

```bash
# Normal request (no alerts)
GET /api/tickets?status=open

# With topic alerts
GET /api/tickets?status=open&topic_alerts=chargeback,fraud,unauthorized

# Response includes match info
{
  "tickets": [...],
  "topic_alerts_active": ["chargeback", "fraud", "unauthorized"],
  "matches": 3  // Count of tickets matching alerts
}
```

### Philosophy

Topic Alerts maintain the AI-First philosophy:
- **Temporary** intent-setting, not permanent sorting
- **Additive** boost to existing smart order
- **Simple** interface (comma-separated text)
- **Automatic** matching and prioritization

## Development

### Project Structure

```
backend/
├── app/
│   ├── api/              # API endpoints
│   │   ├── tickets.py    # Ticket endpoints
│   │   └── ai.py         # AI endpoints
│   ├── services/         # Business logic
│   │   ├── scoring_service.py    # Smart ordering
│   │   └── ai_service.py         # Draft generation
│   ├── models/           # Database models (TODO)
│   ├── tasks/            # Celery background jobs (TODO)
│   ├── core/             # Configuration
│   │   └── config.py     # Settings management
│   └── main.py           # FastAPI app
├── tests/                # Tests (TODO)
├── requirements.txt      # Dependencies
├── .env.example          # Environment template
└── README.md             # This file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# With coverage
pytest --cov=app tests/
```

### Code Style

```bash
# Format code
black app/

# Check linting
flake8 app/

# Type checking
mypy app/
```

## Deployment

### Railway (Recommended)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy
railway up
```

### Docker

```bash
# Build image
docker build -t ai-first-crm .

# Run container
docker run -p 8000:8000 --env-file .env ai-first-crm
```

### Environment Variables

Required for production:

```bash
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://...
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://...
CORS_ORIGINS=https://yourfrontend.com
```

## Philosophy in Action

### Before: Manual Sorting

```
Agent thinks: "Let me sort by... priority? Or maybe value? Or age?"
Agent clicks: Sort dropdown → Select option → Apply
Agent wonders: "Did I pick the right sort?"
```

### After: Smart Ordering

```
Agent opens inbox
System shows: Tickets already in perfect order
Agent acts: Click first ticket, respond
```

**Result:** 5 clicks → 1 click. Zero decisions about sorting.

### Before: Template Selection

```
Agent thinks: "Which template should I use?"
Agent clicks: Templates → Browse → Select → Customize → Fill in order#
Agent manually: Looks up order, finds tracking, checks past issues
```

### After: AI Drafts

```
Agent opens ticket
System shows: Context already gathered, draft already written
Agent reviews: Looks good (or clicks regenerate)
Agent acts: Send
```

**Result:** AI does the research, agent does the decision.

## Contributing

This is an internal tool, but the philosophy is open:

**Intelligence Replaces Interface**

Every feature should:
1. Remove UI complexity
2. Make smart decisions invisibly
3. Reduce clicks and cognitive load
4. Maintain agent control (review, not create)

## License

Proprietary - Quimbi AI

## Support

- Documentation: See `/docs` endpoint
- Issues: Report to development team
- Philosophy questions: Read [PHILOSOPHY.md](../PHILOSOPHY.md)

---

**Built with the belief that the best AI is the AI you don't notice.**
