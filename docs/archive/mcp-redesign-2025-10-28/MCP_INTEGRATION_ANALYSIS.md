# MCP Integration Analysis: Slack Bot & Gorgias

**Analysis Date:** 2025-10-28
**System:** Unified Behavioral Segmentation E-commerce Backend

---

## Executive Summary

This document analyzes the Model Context Protocol (MCP) capabilities implemented for both the **Slack bot** and **Gorgias ticketing integration**. The system provides a comprehensive customer analytics platform with AI-powered insights delivered through multiple channels.

**Key Finding:** The MCP layer acts as a unified API that exposes customer behavioral data, churn risk predictions, revenue forecasting, and campaign recommendations. Both integrations leverage this layer but serve different use cases:
- **Slack Bot:** Internal team analytics, proactive insights, campaign planning
- **Gorgias Integration:** Customer support context enrichment, AI-generated responses

---

## 1. MCP Server Core Capabilities

### Location
`mcp_server/segmentation_server.py`

### Core Tools Provided

The MCP server exposes **6 primary tools** for AI agents:

| Tool Name | Purpose | Key Parameters | Return Data |
|-----------|---------|----------------|-------------|
| `get_customer_profile` | Full behavioral profile | `customer_id` | Archetype, segments, LTV, order history, membership strengths |
| `search_customers` | Find customers by criteria | `archetype_id`, `segment_filter`, `limit` | List of matching customer profiles |
| `get_archetype_stats` | Archetype-level analytics | `archetype_id` | Member count, avg LTV, total revenue, behavioral traits |
| `calculate_segment_trends` | Growth/decline analysis | `axis_name`, `segment_name` | Trend data (current state only - needs historical) |
| `predict_churn_risk` | Churn probability calculation | `customer_id` | Risk score (0-1), risk level, factors, retention recommendations |
| `recommend_segments_for_campaign` | Campaign targeting | `goal` (subscription/retention/cross_sell), `max_segments` | Ranked archetype recommendations with reasoning |

### Data Store Architecture

**In-Memory Storage:**
```python
class SegmentationDataStore:
    customers: Dict[str, Dict]      # customer_id -> profile
    archetypes: Dict[str, Dict]     # archetype_id -> archetype info
    segments: Dict[str, List[Dict]] # axis_name -> segments
```

**Customer Profile Structure:**
- Archetype assignment
- Fuzzy segment memberships (all axes)
- Dominant segments per axis
- Membership strengths (strong/moderate/weak)
- Feature vectors per behavioral axis
- Business metrics: LTV, AOV, order count, recency, tenure

**Archetype Structure:**
- Unique archetype ID
- Member count & population percentage
- Dominant segments signature
- Strength tuple (axis + segment + strength)

### Churn Risk Algorithm

The churn prediction uses a weighted scoring model:

```python
risk_score = 0.0
# +0.3 if weak purchase frequency membership
# +0.3 if >90 days since last purchase
# +0.2 if occasional/one-time buyer segment
# +0.2 if "new" customer (higher baseline churn)

Risk Levels:
- LOW: <0.3
- MEDIUM: 0.3-0.5
- HIGH: 0.5-0.7
- CRITICAL: >0.7
```

### Campaign Recommendation Logic

**Goal-Based Targeting:**
- **Subscription:** Targets "routine_buyer" or "consumable_buyer" repurchase behaviors
- **Retention:** Targets archetypes with weak purchase_frequency strength
- **Cross-sell:** Targets "category_loyal" customers for complementary product introduction

**Ranking:** By member count (prioritize larger impact segments)

---

## 2. Backend API Endpoints (FastAPI)

### Location
`backend/main.py` - Lines 547-3670

### MCP HTTP API

#### Core Endpoints

| Endpoint | Method | Purpose | Rate Limit |
|----------|--------|---------|------------|
| `/api/mcp/tools` | GET | List all available MCP tools | None |
| `/api/mcp/query` | POST | Generic MCP tool invocation | 100/hour |
| `/api/mcp/query/natural-language` | POST | AI-powered natural language queries | 50/hour |

#### Customer-Specific Endpoints

| Endpoint | Method | Description | Use Case |
|----------|--------|-------------|----------|
| `/api/mcp/customer/{id}` | GET | Get complete customer profile | Profile lookup |
| `/api/mcp/customer/{id}/churn-risk` | GET | Churn risk prediction | Support agent context |
| `/api/mcp/customer/{id}/next-purchase` | GET | Predict next purchase timing | Engagement timing |
| `/api/mcp/customer/{id}/ltv-forecast` | GET | Forecast LTV over N months | Customer value projection |
| `/api/mcp/customer/random` | GET | Get random customer (testing) | Development/demos |

#### Aggregate Analytics Endpoints

| Endpoint | Method | Description | Business Value |
|----------|--------|-------------|----------------|
| `/api/mcp/churn/aggregate` | GET | System-wide churn analysis | Strategic retention planning |
| `/api/mcp/revenue/forecast` | GET | Revenue projection (N months) | Financial planning |
| `/api/mcp/growth/projection` | GET | Customer base growth forecast | Acquisition targets |
| `/api/mcp/archetypes/top` | GET | Top archetypes by metric | Segment prioritization |
| `/api/mcp/archetypes/growth-projection` | GET | Archetype-level growth trends | Behavioral shift tracking |

#### Campaign & Search Endpoints

| Endpoint | Method | Description | Marketing Use |
|----------|--------|-------------|---------------|
| `/api/mcp/campaigns/recommend` | POST | Campaign target recommendations | Campaign planning |
| `/api/mcp/campaign/{goal}` | GET | Goal-based segment recommendations | Quick campaign setup |
| `/api/mcp/search` | POST | Search customers by archetype/segment | Audience building |
| `/api/mcp/archetype/{id}` | GET | Archetype stats | Segment analysis |

### Natural Language Query Endpoint

**Endpoint:** `POST /api/mcp/query/natural-language`

**Capabilities:**
- Powered by Claude 3.5 Sonnet
- Interprets natural language business questions
- Maps to appropriate MCP tools or database queries
- Classifies into 20+ query types
- Returns structured data + natural language summary

**Supported Query Types:**
- Churn identification, risk analysis
- Revenue forecasting, growth projection
- Customer lookup (by ID, email, name)
- Behavioral analysis, pattern detection
- Product affinity, category trends
- Campaign targeting, retention planning
- RFM analysis, segment comparison
- High-value customer identification
- B2B customer detection

**Security:**
- Rate limited: 50 requests/hour (vs 100/hour for direct MCP calls)
- SQL injection prevention via parameterized queries
- Input sanitization for customer lookups

---

## 3. Slack Bot Integration

### Location
- `integrations/slack/bot.py` - Main bot initialization
- `integrations/slack/handlers.py` - Event handlers
- `integrations/slack/commands.py` - Slash commands
- `integrations/slack/formatters.py` - Response formatting
- `integrations/slack/conversation_manager.py` - Context management

### Architecture

```
┌─────────────────────────────────────────────────┐
│          Slack Workspace                        │
│  - App mentions (@bot)                          │
│  - Direct messages                              │
│  - Slash commands                               │
│  - Interactive buttons/modals                   │
└────────────┬────────────────────────────────────┘
             │
             │ Slack Events API / Slack Bolt
             ▼
┌─────────────────────────────────────────────────┐
│      SlackBot (AsyncApp)                        │
│  - Event routing                                │
│  - Command registration                         │
│  - Conversation context management              │
└────────────┬────────────────────────────────────┘
             │
             │ HTTP calls to analytics API
             ▼
┌─────────────────────────────────────────────────┐
│   Backend API (/api/mcp/*)                      │
│  - Natural language query endpoint              │
│  - Specific MCP tool endpoints                  │
└────────────┬────────────────────────────────────┘
             │
             │ In-process function calls
             ▼
┌─────────────────────────────────────────────────┐
│   MCP Server (segmentation_server.py)           │
│  - Customer profiles                            │
│  - Churn predictions                            │
│  - Campaign recommendations                     │
└─────────────────────────────────────────────────┘
```

### Interaction Methods

#### 1. App Mentions (@bot in channels)

**Handler:** `@app.event("app_mention")` in `handlers.py:50`

**Flow:**
1. User mentions bot in channel: `@bot which customers are at high churn risk?`
2. Extract query text (remove bot mention)
3. Call `bot.query_analytics_api(query)` → hits `/api/mcp/query/natural-language`
4. Response classified by query type (20+ types)
5. Type-specific formatting via `SlackFormatter`
6. Send formatted Slack blocks back to channel

**Supported in mentions:**
- Churn risk queries
- Revenue forecasts
- Seasonal behavior analysis
- Campaign targeting questions
- General analytics questions

#### 2. Direct Messages (DMs)

**Handler:** `@app.event("message")` in `handlers.py:128`

**Enhanced Capabilities:**
- **Conversational Context:** Maintains user-specific conversation state
- **Clarification Questions:** Bot can ask follow-up questions
- **Multi-turn Conversations:** Remembers previous queries

**Example Flow:**
```
User: "Show me high-value customers"
Bot: "I found several high-value segments. Which metric matters most?
      1. Highest lifetime value
      2. Most frequent purchasers
      3. Highest average order value"
User: "2"
Bot: [Shows frequent purchaser data]
```

**Context Management:**
- `ConversationManager` tracks:
  - Last query per user
  - Pending clarifications
  - Selected options
- Timeout: Context expires after idle period

#### 3. Slash Commands

**Commands Registered:**

| Command | Description | Example | Backend Call |
|---------|-------------|---------|--------------|
| `/churn-check` | Quick churn risk report | `/churn-check` | "which customers are at high churn risk" |
| `/revenue-forecast [time]` | Revenue projection | `/revenue-forecast Q4` | "revenue forecast for Q4" |
| `/seasonal-analysis [event]` | Seasonal patterns | `/seasonal-analysis halloween` | "which customers engaged during halloween" |
| `/campaign-targets [type]` | Campaign recommendations | `/campaign-targets retention` | "who should we target for retention campaign" |
| `/tickets [filter]` | View support tickets | `/tickets urgent` | Queries ticketing system directly |
| `/cs-help` | Show bot help | `/cs-help` | Static help message |

**Technical Details:**
- All slash commands are async (`@app.command`)
- Immediate acknowledgment via `await ack()`
- Background processing + response via `await say()`
- Error handling with formatted error blocks

#### 4. Interactive Components

**Ticket Management Buttons:**

Located in `handlers.py:270-432`

| Action ID | Purpose | Behavior |
|-----------|---------|----------|
| `view_ticket_*` | View ticket details | Fetches full ticket + comments from ticketing system |
| `resolve_ticket_*` | Mark ticket as solved | Updates ticket status to "closed" |
| `hold_ticket_*` | Put ticket on hold | Updates ticket status to "hold" |
| `comment_ticket_*` | Add comment | Opens modal for comment input |

**Modal Submission:**
- `@app.view("comment_modal_*")` handles comment submission
- Extracts ticket ID from callback_id
- Posts comment to ticketing system
- Notifies channel of successful comment

### MCP Capabilities Exposed to Slack

#### Query Types Supported (20+)

**Customer Intelligence:**
1. **Churn Risk Analysis** - Identifies at-risk customers
2. **High-Value Customer Identification** - Top spenders, top LTV
3. **Customer Lookup** - Find customer by ID/email/name
4. **Behavioral Analysis** - Purchase patterns, engagement trends
5. **RFM Analysis** - Recency, Frequency, Monetary segmentation

**Revenue & Growth:**
6. **Revenue Forecasting** - Monthly/quarterly projections
7. **Growth Projections** - Customer base expansion forecasts
8. **Archetype Growth Trends** - Which segments are growing/declining

**Campaign Planning:**
9. **Campaign Targeting** - Who to target for specific campaign goals
10. **Seasonal Recommendations** - Event-based customer engagement
11. **Retention Action Plans** - Specific retention strategies
12. **Winback Recommendations** - Re-engagement strategies

**Product & Category:**
13. **Product Affinity** - What customers buy together
14. **Category Trends** - Category popularity over time
15. **Product Performance** - Individual product analytics

**Behavioral Patterns:**
16. **One-Time Buyers** - Single-purchase customers
17. **Momentum Analysis** - Customers with increasing engagement
18. **Declining Engagement** - Customers reducing activity
19. **Discount Dependency** - Customers who only buy on sale

**Operational:**
20. **B2B Identification** - Detect bulk/business buyers
21. **Segment Comparison** - Compare archetype performance

### Response Formatting

**SlackFormatter** (`formatters.py`) provides specialized formatting for each query type:

**Example: Churn Response Format**
```python
{
    "blocks": [
        {"type": "header", "text": "⚠️ High Churn Risk Customers"},
        {"type": "section", "text": "Found 234 customers at risk..."},
        {"type": "divider"},
        # Customer list with:
        # - Customer ID
        # - Risk score with color-coded emoji
        # - LTV
        # - Days since last purchase
        # - Action buttons
    ]
}
```

**Visual Elements:**
- Color-coded risk levels (🔴 Critical, 🟡 High, 🟢 Low)
- Progress bars for metrics
- Action buttons for ticket creation
- Contextual help text
- Monetary formatting ($X,XXX.XX)
- Percentage formatting with trends (↑ ↓)

### Security & Rate Limiting

**Slack Bot Token Security:**
- Bot token stored in environment variable `SLACK_BOT_TOKEN`
- Signing secret validates all incoming requests
- Socket Mode option for local development (no public endpoint)

**API Rate Limits:**
- Natural language queries: 50/hour (expensive AI calls)
- Direct MCP calls: 100/hour
- Implemented via SlowAPI middleware

**Authentication:**
- Slack verifies all requests via signing secret
- Backend API requires valid session (if deployed with auth)

---

## 4. Gorgias AI Assistant Integration

### Location
`integrations/gorgias_ai_assistant.py`

### Architecture

```
┌─────────────────────────────────────────────────┐
│          Gorgias (Support Ticket System)        │
│  - New ticket created                           │
│  - Customer message added                       │
│  - Webhook triggered                            │
└────────────┬────────────────────────────────────┘
             │
             │ HTTPS POST with HMAC-SHA256 signature
             ▼
┌─────────────────────────────────────────────────┐
│   Backend Webhook Endpoint                      │
│   (Receives & validates Gorgias webhook)        │
└────────────┬────────────────────────────────────┘
             │
             │ Pass webhook payload
             ▼
┌─────────────────────────────────────────────────┐
│   GorgiasAIAssistant.handle_ticket_webhook()    │
│  1. Extract customer ID                         │
│  2. Fetch customer analytics via MCP API        │
│  3. Generate AI draft reply (Claude Haiku)      │
│  4. Post draft as internal note to ticket       │
└────────────┬────────────────────────────────────┘
             │
             ├──── MCP API Call ────►  /api/mcp/customer/{id}
             │                        /api/mcp/customer/{id}/churn-risk
             │
             └──── Gorgias API ────►  POST /tickets/{id}/messages
```

### Workflow Breakdown

#### Step 1: Webhook Reception & Validation

**Trigger Events:**
- New ticket created
- New message added to existing ticket
- Customer reply received

**Security:**
```python
def validate_webhook_signature(payload: bytes, signature_header: str) -> bool:
    # Extract signature from header: "sha256=abc123..."
    algorithm, signature = signature_header.split("=", 1)

    # Compute HMAC-SHA256
    expected = hmac.new(
        key=GORGIAS_WEBHOOK_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Constant-time comparison (prevents timing attacks)
    return hmac.compare_digest(signature, expected)
```

**Critical Configuration:**
- Environment variable: `GORGIAS_WEBHOOK_SECRET`
- Must match webhook secret configured in Gorgias dashboard
- Validates authenticity of all webhook requests

#### Step 2: Customer Identification

**Priority Order:**
1. **external_id** - Shopify customer ID (most reliable)
2. **meta.shopify_customer_id** - Alternative Shopify ID location
3. **id** - Gorgias customer ID
4. **email** - Fallback for lookup

**Code Location:** `gorgias_ai_assistant.py:188`

```python
def _extract_customer_id(customer_data: Dict) -> Optional[str]:
    return (
        customer_data.get("external_id") or
        customer_data.get("meta", {}).get("shopify_customer_id") or
        customer_data.get("id") or
        customer_data.get("email")
    )
```

#### Step 3: Analytics Enrichment

**MCP Endpoints Called:**

1. **Customer Profile:** `GET /api/mcp/customer/{customer_id}`
   - Returns: Archetype, segments, LTV, order history, tenure

2. **Churn Risk:** `GET /api/mcp/customer/{customer_id}/churn-risk`
   - Returns: Risk score, risk level, risk factors, recommendations

**Data Combined Into Context:**
```python
{
    "customer_id": "12345",
    "profile": { /* Full profile data */ },
    "churn": { /* Churn risk analysis */ },
    "fetched_at": "2025-10-28T12:34:56Z"
}
```

**Fallback for Unknown Customers:**
If customer not found in analytics system:
```python
{
    "is_new": True,
    "name": customer_data.get("name"),
    "email": customer_data.get("email"),
    "profile": {},
    "churn": {}
}
```

#### Step 4: Analytics Summary Generation

**Purpose:** Create internal context for CS agent (NOT shared with customer)

**Code Location:** `gorgias_ai_assistant.py:358`

**Metric Categorization:**

| Metric | Thresholds | Categories |
|--------|-----------|------------|
| **LTV** | $5000+ / $2000-5000 / $500-2000 / $0-500 | VIP / High Value / Mid Value / Standard |
| **Churn Risk** | 70%+ / 50-70% / 30-50% / <30% | CRITICAL / ELEVATED / MODERATE / LOW |
| **Engagement** | Days since last purchase | Active (<30d) / Recently Active (<60d) / Cooling Down (<90d) / At Risk (90d+) |

**Example Summary Output:**
```
📊 CUSTOMER INSIGHTS (Internal - Do Not Share)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Lifetime Value: $3,450 (High Value)
⚠️  Churn Risk: 65% (ELEVATED - Monitor Closely)
📈 Historical: 12 orders, $287 avg order
📅 Last Purchase: 45 days ago (Recently Active)
🎯 Pattern: Seasonal buyer - shops during key periods

⚠️ RETENTION STRATEGY: Valuable customer showing early churn signals.
   Prioritize quick resolution and consider retention offer.
```

**Behavioral Pattern Inference:**
```python
if total_orders >= 10:
    if avg_days_between < 30:
        "Frequent, regular buyer - highly engaged"
    elif avg_days_between < 90:
        "Seasonal buyer - shops during key periods"
    else:
        "Occasional buyer - large gaps between purchases"
elif total_orders >= 3:
    "Building relationship - still exploring products"
elif total_orders > 0:
    "Recent first-time buyer"
```

**Retention Recommendations:**

| LTV | Churn Risk | Recommendation |
|-----|-----------|----------------|
| $2000+ | 70%+ | ⚠️ RETENTION PRIORITY: Maximum intervention, VIP treatment |
| $2000+ | 50%+ | 💡 RETENTION STRATEGY: Quick resolution, retention offer |
| Any | 70%+ | ⚠️ RETENTION ALERT: Exceptional service, quick resolution |
| $2000+ | Low | ✨ VIP CUSTOMER: Maintain excellent service quality |

#### Step 5: AI Draft Reply Generation

**LLM:** Claude 3.5 Haiku (`claude-3-5-haiku-20241022`)
- **Cost:** Cheapest Claude model (~$0.25/MTok input, $1.25/MTok output)
- **Speed:** Fast response time (<2s)
- **Quality:** Professional customer service responses

**Prompt Structure:**

```
You are a professional customer service agent for a quilting e-commerce company.

CUSTOMER ANALYTICS (Use for context, DO NOT share specifics):
[Analytics summary from Step 4]

CUSTOMER'S MESSAGE:
[Customer's actual message text]

TICKET CATEGORY: [Detected category]

INSTRUCTIONS:
1. Be warm, professional, and empathetic
2. Address their specific concern directly
3. If you have purchase history information, reference it naturally
4. For high-value customers at churn risk, be extra accommodating
5. For new customers, be welcoming and helpful
6. Offer specific next steps or solutions
7. Keep response concise (3-5 paragraphs max)
8. Use the customer's name: [Customer Name]
9. Do NOT mention "churn risk", "LTV", "analytics" or any internal metrics
10. Do NOT use the customer analytics section verbatim - extract relevant context only
```

**Ticket Category Detection:**

Auto-detects ticket type to guide response:

| Keywords | Category |
|----------|----------|
| "return", "refund", "send back" | Return/Exchange Request |
| "broken", "damaged", "defective", "wrong item" | Product Issue - Damaged/Wrong Item |
| "where is", "tracking", "hasn't arrived" | Order Status/Delivery Inquiry |
| "how to", "question about", "wondering" | Product Question |
| "cancel", "change order", "modify" | Order Modification |
| (default) | General Inquiry |

**Response Tone Adaptation:**

Based on customer analytics:
- **High LTV + High Churn Risk:** Extra accommodating, immediate action, generous solutions
- **High LTV + Low Churn Risk:** Maintain VIP quality, professional warmth
- **Low LTV + High Churn Risk:** Exceptional service, quick resolution
- **New Customer:** Welcoming, educational, patience

**Example Output:**

```
Hi Sarah,

Thank you so much for reaching out about your order! I can see you've been a valued customer
with us for over a year now, and I really appreciate your continued support.

I'm looking into the tracking information for your order #12345 right now. I notice it's been
45 days since your last purchase - I hope everything has been going well!

Let me get this sorted out for you immediately. I'm escalating this to our shipping team and
will have an update for you within the next 2 hours. In the meantime, I'd like to offer you
a 15% discount on your next order as a thank you for your patience.

Would that work for you? I'm here to help!

Best regards,
Customer Success Team
```

**Fallback Response:**

If Claude API fails:
```python
def _generate_fallback_response(customer_message, customer_data):
    return f"""Hi {name},

Thank you for reaching out to us! I've received your message and I'm here to help.

I'm looking into your inquiry right now and will get back to you with a detailed response shortly.

In the meantime, if you have any additional information that might help me assist you better,
please feel free to share it.

Best regards,
Customer Success Team"""
```

#### Step 6: Post Draft to Gorgias

**API Call:** `POST /tickets/{ticket_id}/messages`

**Payload:**
```json
{
    "channel": "api",
    "via": "api",
    "source": {
        "type": "api",
        "to": [],
        "from": {"address": "ai-assistant@quimbi.com"}
    },
    "body_text": "[Analytics Summary]\n\n━━━━━━━━━━━━━━\n\n[Draft Reply]",
    "is_note": true  // ← Internal note, NOT sent to customer
}
```

**Critical:** `is_note: true` means:
- Draft is visible ONLY to support agents
- Customer does NOT see the draft
- Agent can review, edit, and send when ready
- Agent sees customer analytics context

**Authentication:**
- HTTP Basic Auth using Gorgias username + API key
- Credentials: `(gorgias_username, gorgias_api_key)`

### MCP Capabilities Exposed to Gorgias

**Direct MCP Endpoints Used:**

1. **Customer Profile Lookup**
   - Endpoint: `/api/mcp/customer/{customer_id}`
   - Purpose: Get complete behavioral profile
   - Used For: Purchase history, segment membership, behavioral traits

2. **Churn Risk Prediction**
   - Endpoint: `/api/mcp/customer/{customer_id}/churn-risk`
   - Purpose: Calculate churn probability
   - Used For: Retention strategy recommendations, response urgency

**Indirect MCP Usage (via AI):**

The Claude-generated responses implicitly use MCP data:
- **Purchase Frequency:** Mentioned in responses ("I see you shop with us regularly")
- **Customer Tenure:** Referenced for relationship building ("valued customer for over a year")
- **Order History:** Contextualizes support issues ("regarding your recent order")
- **Value Tier:** Influences compensation offered (VIP customers get better offers)

**NOT Currently Used (Future Opportunities):**

- `predict_next_purchase` - Could suggest proactive offers
- `forecast_customer_ltv` - Could justify retention investments
- `recommend_segments_for_campaign` - Could trigger cross-sell opportunities
- `search_customers` - Could find similar customer issues

### Configuration Requirements

**Environment Variables:**

```bash
# Gorgias API Credentials
GORGIAS_DOMAIN="yourcompany"  # Domain name in Gorgias
GORGIAS_USERNAME="agent@yourcompany.com"  # Gorgias account email
GORGIAS_API_KEY="xxx"  # API key from Gorgias settings

# Webhook Security
GORGIAS_WEBHOOK_SECRET="xxx"  # Webhook signing secret

# Analytics Backend
ANALYTICS_API_URL="https://your-backend.railway.app"  # Backend API URL

# AI Service
ANTHROPIC_API_KEY="sk-ant-xxx"  # Claude API key
```

**Gorgias Webhook Setup:**

1. Go to Gorgias Settings → HTTP Integration
2. Create new webhook for "Ticket Created" and "Message Created" events
3. Set URL to: `https://your-backend.railway.app/webhooks/gorgias`
4. Copy webhook secret to `GORGIAS_WEBHOOK_SECRET`
5. Enable webhook

### Error Handling & Edge Cases

**Unknown Customer:**
- Creates default analytics profile
- AI response is still generated (generic, welcoming)
- No churn risk data available

**Analytics API Failure:**
- Falls back to default profile
- Logs error for monitoring
- Does NOT block ticket processing

**Claude API Failure:**
- Uses simple fallback template
- Logs error for monitoring
- Does NOT block ticket processing

**Gorgias API Failure:**
- Returns error status
- Logged for retry/manual intervention
- Does NOT break webhook handler

**No Customer Messages:**
- Skips processing (status: "skipped", reason: "no_customer_message")
- No draft generated
- Agent handles manually

---

## 5. Comparison: Slack vs Gorgias MCP Usage

| Aspect | Slack Bot | Gorgias Integration |
|--------|-----------|---------------------|
| **Primary User** | Internal CS team, managers | External customers (via CS agents) |
| **Interaction Model** | Proactive queries, analytics exploration | Reactive support context enrichment |
| **MCP Endpoint Usage** | All endpoints (20+ query types) | Customer profile + churn risk only |
| **AI Model** | Claude 3.5 Sonnet (reasoning) | Claude 3.5 Haiku (speed + cost) |
| **Data Visibility** | Full analytics visible to team | Analytics hidden from customer |
| **Response Type** | Structured data + charts + tables | Natural language support responses |
| **Real-time Requirements** | Medium (few seconds OK) | High (fast response critical) |
| **Rate Limiting** | 50-100/hour | None (triggered by tickets) |
| **Cost per Query** | $0.02-0.05 (Sonnet) | $0.002-0.005 (Haiku) |
| **Conversation State** | Stateful (multi-turn) | Stateless (per-ticket) |

### Use Case Alignment

**Slack Bot - Best For:**
- ✅ Strategic planning (revenue forecasts, growth projections)
- ✅ Campaign targeting (who to email for retention/cross-sell)
- ✅ Churn risk monitoring (weekly check-ins)
- ✅ Ad-hoc customer lookups (internal team queries)
- ✅ Behavioral analysis (what's trending, what's declining)
- ✅ Reporting (automated daily/weekly summaries)

**Gorgias Integration - Best For:**
- ✅ Real-time support context (customer value, churn risk)
- ✅ Response personalization (VIP treatment for high-value)
- ✅ Retention alerts (flag at-risk customers to agents)
- ✅ Draft generation (AI-powered response suggestions)
- ✅ Escalation routing (high-value customers get priority)
- ✅ Training (show agents how to tailor responses)

---

## 6. Data Flow Diagrams

### Slack Bot Data Flow

```
┌──────────────┐
│ Slack User   │
│ Types Query  │
└──────┬───────┘
       │
       │ "@bot which customers at churn risk?"
       ▼
┌──────────────────────────┐
│ Slack Bolt Handler       │
│ (app_mention event)      │
└──────┬───────────────────┘
       │
       │ HTTP POST
       ▼
┌──────────────────────────────────────┐
│ /api/mcp/query/natural-language      │
│ - Parse query with Claude Sonnet     │
│ - Classify query type                │
│ - Route to appropriate MCP tool      │
└──────┬───────────────────────────────┘
       │
       ├─► /api/mcp/churn/aggregate
       │   - Get high-risk customers
       │   - Calculate risk scores
       │   - Aggregate statistics
       │
       └─► Returns structured JSON:
           {
             "query_type": "churn_identification",
             "answer": {
               "at_risk_count": 234,
               "critical_risk_count": 45,
               "customers": [...],
               "aggregates": {...}
             }
           }
       │
       ▼
┌──────────────────────────┐
│ SlackFormatter           │
│ - Format as Slack blocks │
│ - Add color coding       │
│ - Add action buttons     │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ Slack Channel            │
│ Rich formatted response  │
│ with tables, charts,     │
│ buttons, and context     │
└──────────────────────────┘
```

### Gorgias Integration Data Flow

```
┌──────────────────┐
│ Customer Sends   │
│ Email to Support │
└──────┬───────────┘
       │
       ▼
┌──────────────────────────┐
│ Gorgias Creates Ticket   │
│ Triggers Webhook         │
└──────┬───────────────────┘
       │
       │ HTTPS POST + HMAC Signature
       ▼
┌────────────────────────────────────┐
│ Backend Webhook Handler            │
│ 1. Validate HMAC-SHA256 signature  │
│ 2. Extract customer ID             │
└──────┬─────────────────────────────┘
       │
       │ Parallel API Calls
       ├─► /api/mcp/customer/{id}
       │   - Get profile, LTV, orders
       │   - Get archetype & segments
       │
       └─► /api/mcp/customer/{id}/churn-risk
           - Get risk score
           - Get risk factors
       │
       ▼
┌────────────────────────────────────┐
│ Build Analytics Summary            │
│ - Categorize LTV (VIP/High/Mid)    │
│ - Categorize churn risk            │
│ - Infer behavioral pattern         │
│ - Generate retention recommendation│
└──────┬─────────────────────────────┘
       │
       ▼
┌────────────────────────────────────┐
│ Generate Draft with Claude Haiku   │
│ Prompt:                            │
│ - Customer analytics (internal)    │
│ - Customer message                 │
│ - Instructions for tone            │
└──────┬─────────────────────────────┘
       │
       ▼
┌────────────────────────────────────┐
│ Post Draft to Gorgias              │
│ POST /tickets/{id}/messages        │
│ {                                  │
│   "body_text": "Summary\n\nDraft", │
│   "is_note": true                  │
│ }                                  │
└──────┬─────────────────────────────┘
       │
       ▼
┌────────────────────────────────────┐
│ CS Agent Sees:                     │
│ - Customer analytics context       │
│ - AI-generated draft reply         │
│ - Retention recommendation         │
│                                    │
│ Agent can:                         │
│ - Edit draft                       │
│ - Send as-is                       │
│ - Ignore and write custom          │
└────────────────────────────────────┘
```

---

## 7. Performance & Scalability

### Response Times

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Slack natural language query | 2-5 seconds | Claude Sonnet inference + MCP lookup |
| Slack slash command | 1-3 seconds | Direct MCP endpoint (no LLM) |
| Gorgias draft generation | 3-6 seconds | Claude Haiku inference + MCP lookup |
| MCP customer profile lookup | <100ms | In-memory data store |
| MCP churn prediction | <200ms | In-memory calculation |
| MCP search (100 customers) | <500ms | In-memory filtering |

### Bottlenecks

**Current Limitations:**
1. **MCP Data Store:** In-memory only - lost on restart
   - **Impact:** Requires reload from discovery results on startup
   - **Mitigation:** Cache discovery results to disk/database

2. **No Historical Data:** Trend analysis not yet implemented
   - **Impact:** `calculate_segment_trends` returns "N/A"
   - **Mitigation:** Store periodic snapshots for time-series analysis

3. **Single-Instance Only:** No distributed caching
   - **Impact:** Each server instance has its own data store
   - **Mitigation:** Use Redis for shared cache across instances

4. **Sequential Webhook Processing:** No queue
   - **Impact:** High ticket volume could cause timeouts
   - **Mitigation:** Implement background job queue (Celery/RQ)

### Scalability Recommendations

**Short-term (0-1000 customers/day):**
- ✅ Current architecture sufficient
- Monitor Claude API rate limits
- Monitor Railway memory usage

**Medium-term (1000-10000 customers/day):**
- Implement Redis cache for customer profiles
- Add background job queue for Gorgias webhooks
- Implement result caching for common queries
- Upgrade to Railway Pro plan for more memory

**Long-term (10000+ customers/day):**
- Migrate MCP data store to PostgreSQL with materialized views
- Implement read replicas for analytics queries
- Add CDN for static assets
- Consider dedicated AI inference server
- Implement rate limiting per customer/tenant

---

## 8. Security Considerations

### Authentication & Authorization

**Slack Bot:**
- ✅ Signing secret validates all requests
- ✅ Bot token stored securely in env vars
- ✅ Socket Mode option avoids public endpoint
- ⚠️ No user-level permissions (all Slack users have equal access)
- **Recommendation:** Implement role-based access control (RBAC)

**Gorgias Webhook:**
- ✅ HMAC-SHA256 signature validation
- ✅ Constant-time comparison prevents timing attacks
- ✅ Webhook secret stored securely
- ✅ Validates payload authenticity
- **Strong:** Industry-standard webhook security

**Backend API:**
- ✅ Rate limiting on natural language queries (50/hour)
- ✅ Rate limiting on MCP queries (100/hour)
- ⚠️ No authentication on MCP endpoints (deployed publicly)
- **Recommendation:** Add API key authentication for production

### Data Privacy & PII

**Customer Data Exposure:**

| Data Type | Slack Bot | Gorgias | Mitigation |
|-----------|-----------|---------|------------|
| Customer IDs | ✅ Visible | ✅ Visible | Hashed IDs in logs |
| Email addresses | ✅ Visible | ✅ Visible | Obfuscate in responses |
| Purchase history | ✅ Full access | ✅ Full access | Role-based access |
| PII (name, address) | ❌ Not exposed | ✅ Exposed | Already protected |
| Payment info | ❌ Not stored | ❌ Not stored | N/A |

**GDPR/CCPA Considerations:**
- Customer data used for legitimate business purpose (support, analytics)
- Data retention policy needed for MCP cache
- Right to deletion must cascade to MCP data store
- Data processing agreement with Anthropic (Claude API)

**Recommendations:**
1. Implement data retention policy (delete old profiles after X days)
2. Add customer consent tracking
3. Implement right-to-deletion API endpoint
4. Audit log all customer data access
5. Encrypt customer profiles at rest

### API Security

**SQL Injection:**
- ✅ Natural language query uses parameterized queries
- ✅ Input sanitization on customer lookups
- ✅ No raw SQL construction from user input

**Prompt Injection:**
- ⚠️ Slack queries passed directly to Claude
- ⚠️ Customer messages in Gorgias passed to Claude
- **Mitigation:** Claude has built-in prompt injection defenses
- **Recommendation:** Add input validation for suspicious patterns

**Rate Limiting:**
- ✅ SlowAPI middleware in place
- ✅ Different limits for AI vs direct queries
- ⚠️ No per-user rate limiting
- **Recommendation:** Track by Slack user ID or Gorgias agent

**Secrets Management:**
- ✅ All secrets in environment variables
- ✅ Not committed to git (.env in .gitignore)
- ⚠️ No secret rotation policy
- **Recommendation:** Use secret management service (AWS Secrets Manager, HashiCorp Vault)

---

## 9. Cost Analysis

### Per-Query Costs

**Claude API Pricing:**
- **Sonnet 3.5:** $3/MTok input, $15/MTok output
- **Haiku 3.5:** $0.25/MTok input, $1.25/MTok output

**Slack Bot (Claude Sonnet):**
- Average query: ~500 tokens input, ~1000 tokens output
- Cost per query: $0.0015 + $0.015 = **$0.0165 per query**
- At 1000 queries/month: **$16.50/month**

**Gorgias Integration (Claude Haiku):**
- Average ticket: ~1000 tokens input, ~400 tokens output
- Cost per ticket: $0.00025 + $0.0005 = **$0.00075 per ticket**
- At 1000 tickets/month: **$0.75/month**

**Infrastructure (Railway):**
- Hobby plan: $5/month (500MB memory, limited hours)
- Pro plan: $20/month (2GB memory, unlimited)
- Database: Free (PostgreSQL Hobby)

### Monthly Cost Projection

| Usage Level | Slack Queries | Gorgias Tickets | Claude API Cost | Railway Cost | **Total** |
|-------------|---------------|-----------------|-----------------|--------------|-----------|
| **Startup** | 500 | 500 | $8.62 | $5 | **$13.62** |
| **Small Business** | 2000 | 2000 | $34.50 | $20 | **$54.50** |
| **Mid-Market** | 10000 | 5000 | $168.75 | $20 | **$188.75** |
| **Enterprise** | 50000 | 20000 | $840.00 | $50+ | **$890+** |

**Cost Optimization Opportunities:**
1. Cache common query results (reduce Claude API calls)
2. Use cheaper models for simple queries (Haiku instead of Sonnet)
3. Batch processing for non-urgent webhooks
4. Implement query result TTL cache

---

## 10. Future Enhancement Opportunities

### Slack Bot Enhancements

**1. Scheduled Reports**
- Daily churn risk summary
- Weekly revenue forecast
- Monthly segment growth report
- Automated alerts for metric thresholds

**2. Interactive Dashboards**
- Embed charts/graphs in Slack
- Real-time metric updates
- Drill-down capabilities via buttons

**3. Workflow Automation**
- Create campaigns directly from Slack
- Trigger email sequences
- Auto-create retention tickets for at-risk customers

**4. Multi-Channel Support**
- Microsoft Teams integration
- Discord integration
- Telegram integration

**5. Advanced Query Types**
- Cohort analysis
- A/B test analysis
- Subscription cancellation prediction
- Customer lifetime value optimization

### Gorgias Enhancements

**1. Proactive Suggestions**
- Recommend upsell products based on profile
- Suggest win-back offers for at-risk customers
- Predict next purchase timing → proactive outreach

**2. Automated Actions**
- Auto-escalate VIP customer tickets
- Auto-apply discount codes for retention
- Auto-tag tickets by churn risk level

**3. Agent Training**
- Highlight key phrases for different customer tiers
- Suggest response templates by archetype
- Real-time feedback on response quality

**4. Multi-Ticket Context**
- Track customer support history
- Identify repeat issues
- Escalation trigger based on ticket count

**5. Sentiment Analysis**
- Detect frustrated customers
- Route to senior agents
- Prioritize negative sentiment tickets

### MCP Server Enhancements

**1. Historical Trend Analysis**
- Store periodic snapshots of customer profiles
- Calculate segment growth rates
- Detect behavioral shifts over time
- Implement `calculate_segment_trends` properly

**2. Predictive Models**
- Next-purchase date prediction (improved)
- LTV forecasting with confidence intervals
- Product recommendation engine
- Subscription conversion probability

**3. Real-Time Updates**
- Webhook triggers for data updates
- Incremental profile updates (not full reload)
- Event stream processing (Kafka/Redis Streams)

**4. Multi-Tenant Support**
- Separate data stores per client
- Tenant-specific rate limiting
- Custom archetype definitions per tenant

**5. Advanced Search**
- Full-text search on customer attributes
- Complex filtering (AND/OR/NOT logic)
- Geolocation-based search
- Cohort building UI

### Integration Enhancements

**1. Zendesk Integration**
- Similar to Gorgias (ticket context enrichment)
- Automated ticket routing by customer value
- Churn risk tagging

**2. Email Platform Integration (Klaviyo, Mailchimp)**
- Sync customer segments
- Trigger campaigns based on behavioral changes
- A/B test recommendations

**3. CRM Integration (HubSpot, Salesforce)**
- Sync customer profiles
- Update lead scores based on churn risk
- Enrich contact records with archetypes

**4. Data Warehouse Integration**
- Export profiles to Snowflake/BigQuery
- Scheduled data syncs
- BI tool connectivity (Looker, Tableau)

**5. Payment Processor Integration (Stripe, Shopify)**
- Real-time transaction updates
- Subscription event handling
- Payment failure churn prediction

---

## 11. Technical Debt & Maintenance

### Current Technical Debt

**High Priority:**
1. ❌ **MCP data store is in-memory only** - Lost on restart
   - **Fix:** Persist to PostgreSQL or Redis
   - **Effort:** Medium (1-2 days)

2. ❌ **No historical snapshots** - Can't track trends
   - **Fix:** Implement periodic snapshot storage
   - **Effort:** High (3-5 days)

3. ❌ **No authentication on MCP endpoints** - Publicly accessible
   - **Fix:** Add API key middleware
   - **Effort:** Low (1 day)

**Medium Priority:**
4. ⚠️ **No retry logic for Gorgias webhooks** - Lost on failure
   - **Fix:** Implement exponential backoff retry
   - **Effort:** Low (1 day)

5. ⚠️ **No per-user rate limiting** - All Slack users share limit
   - **Fix:** Track by Slack user ID
   - **Effort:** Low (1 day)

6. ⚠️ **Slack bot has no RBAC** - All users have equal access
   - **Fix:** Implement permission checks
   - **Effort:** Medium (2-3 days)

**Low Priority:**
7. ℹ️ **No caching for common queries** - Repeated Claude API calls
   - **Fix:** Implement Redis cache with TTL
   - **Effort:** Medium (2 days)

8. ℹ️ **No monitoring/alerting** - No visibility into errors
   - **Fix:** Add Sentry, Datadog, or similar
   - **Effort:** Low (1 day)

### Maintenance Checklist

**Weekly:**
- [ ] Review error logs for Slack bot
- [ ] Review error logs for Gorgias webhooks
- [ ] Check Claude API usage vs budget
- [ ] Monitor Railway resource usage

**Monthly:**
- [ ] Review and update archetype definitions
- [ ] Analyze query patterns for optimization
- [ ] Check for security updates (dependencies)
- [ ] Review rate limiting effectiveness

**Quarterly:**
- [ ] Audit customer data retention
- [ ] Review and optimize Claude prompts
- [ ] Performance testing under load
- [ ] Cost optimization analysis

---

## 12. Conclusion

### Summary of MCP Capabilities

**Core Strengths:**
1. ✅ **Unified API Layer** - Single source of truth for customer analytics
2. ✅ **Multi-Channel Integration** - Slack + Gorgias working from same data
3. ✅ **AI-Powered Insights** - Natural language queries + draft generation
4. ✅ **Real-Time Analytics** - Fast in-memory data store
5. ✅ **Modular Architecture** - Easy to add new integrations

**Key Differentiators:**
- Behavioral segmentation (not just RFM)
- Churn prediction with actionable recommendations
- Context-aware customer support (Gorgias)
- Conversational analytics (Slack)
- Campaign targeting with reasoning

### Business Value Delivered

**For Customer Success Teams:**
- Reduce time to find at-risk customers (from hours to seconds)
- Personalize support responses based on customer value
- Proactive retention strategies
- Data-driven campaign targeting

**For Customers:**
- Faster, more personalized support
- VIP treatment for high-value customers
- Relevant product recommendations
- Consistent service quality

**For Business Leadership:**
- Revenue forecasting and growth projections
- Segment-level performance tracking
- Data-driven decision making
- Measurable retention improvements

### Deployment Status

**Production-Ready Components:**
- ✅ MCP server core functionality
- ✅ Backend API endpoints
- ✅ Slack bot (all features)
- ✅ Gorgias integration (webhook + AI)

**Needs Configuration:**
- Environment variables for all integrations
- Slack app installation + OAuth
- Gorgias webhook registration
- Railway deployment

**Recommended Next Steps:**
1. Set up Railway production environment
2. Configure Slack app and install to workspace
3. Register Gorgias webhook
4. Test end-to-end with real customer data
5. Monitor for 1 week, iterate on prompts
6. Roll out to full CS team

---

**Document Version:** 1.0
**Last Updated:** 2025-10-28
**Maintained By:** Development Team
**Review Frequency:** Quarterly
