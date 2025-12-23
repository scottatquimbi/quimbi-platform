# Backend Reference for Frontend Developers

**Date:** 2025-11-12
**Purpose:** Complete guide to understanding the Quimbi backend system, its math, endpoints, and data structures

---

## Table of Contents

1. [What is Quimbi?](#what-is-quimbi)
2. [Current System Status](#current-system-status)
3. [Core Concepts](#core-concepts)
4. [The Math Behind Behavioral Segmentation](#the-math-behind-behavioral-segmentation)
5. [Data Structures](#data-structures)
6. [Complete API Reference](#complete-api-reference)
7. [Common Use Cases](#common-use-cases)
8. [Frontend Integration Examples](#frontend-integration-examples)

---

## What is Quimbi?

**Quimbi is a Customer Intelligence Platform that analyzes e-commerce purchase behavior to:**

1. **Segment customers** into behavioral groups (archetypes) based on 13 behavioral axes
2. **Predict churn** risk for individual customers and aggregate populations
3. **Forecast LTV** (Lifetime Value) and growth trends
4. **Generate insights** via natural language queries using AI
5. **Automate support** by providing customer context to agents

**Key differentiator:** Not demographic segmentation ("women 25-34"), but **behavioral segmentation** ("weekend crafters who hunt for deals").

**Current Status:** 93,564 customers actively segmented with purchase history data.

---

## Current System Status

**Last Updated:** November 12, 2025

### **Segmentation System**

The backend has been updated to the **13-axis behavioral segmentation system**:

| Metric | Value | Notes |
|--------|-------|-------|
| **Total Customer Profiles** | 120,979 | All customers in database |
| **Actively Segmented** | 93,564 (77.3%) | Customers with purchase history |
| **Awaiting Orders** | 27,415 (22.7%) | Customer profiles without orders yet |
| **Behavioral Axes** | 13 | 8 purchase + 5 support axes |
| **Segment Discovery** | Dynamic | Archetypes discovered via clustering |

### **What This Means for Frontend**

**✅ Production Ready:**
- All API endpoints return 13-axis segment data
- All customers with order history have been segmented
- Fuzzy membership scores available for all 13 axes
- Archetypes include all 13 behavioral dimensions

**⚠️ Important Notes:**
- **22.7% of customer profiles** don't have segments yet because they haven't made purchases
- These customers will be automatically segmented when they place their first order
- Frontend should gracefully handle customers without `dominant_segments` data
- Display message: "Awaiting first purchase to analyze behavior"

**🔄 Automatic Updates:**
- New customers are segmented immediately after first purchase
- Existing customers are re-segmented monthly (batch job)
- Real-time updates available via API refresh

---

## Core Concepts

### **1. Behavioral Axes (13 Dimensions)**

Think of each axis as measuring ONE aspect of shopping behavior:

#### **Marketing/Purchase Behavior Axes (8)**

| Axis | What it Measures | Example Segments |
|------|------------------|------------------|
| **purchase_frequency** | How often they shop | "weekly_shopper", "occasional_buyer", "once_a_year" |
| **purchase_value** | How much they spend | "high_value", "mid_tier", "budget_conscious" |
| **category_exploration** | Product variety seeking | "category_explorer", "variety_seeker", "focused_buyer" |
| **price_sensitivity** | Discount dependency | "deal_hunter", "full_price_buyer", "value_focused" |
| **purchase_cadence** | Shopping rhythm/timing | "weekend_buyer", "payday_shopper", "irregular" |
| **customer_maturity** | Customer tenure/lifecycle | "new_customer", "established", "long_term_loyal" |
| **repurchase_behavior** | Loyalty/repeat buying | "highly_loyal", "moderate_repeater", "one_time_buyer" |
| **return_behavior** | Return patterns | "never_returns", "occasional_returner", "frequent_returner" |

#### **Customer Support Behavior Axes (5)**

| Axis | What it Measures | Example Segments |
|------|------------------|------------------|
| **communication_preference** | Support channel usage | "email_preferred", "phone_caller", "self_service" |
| **problem_complexity_profile** | Type of support needed | "simple_questions", "complex_issues", "technical_support" |
| **loyalty_trajectory** | Engagement trend over time | "growing_engagement", "stable", "declining" |
| **product_knowledge** | Expertise level | "expert_user", "intermediate", "beginner" |
| **value_sophistication** | Understanding of product value | "value_aware", "feature_focused", "price_focused" |

**Important:** These are **independent axes**. A customer can be:
- "high_value" + "deal_hunter" + "self_service" (spends a lot, wants discounts, rarely contacts support)
- "weekly_shopper" + "budget_conscious" + "email_preferred" (shops often but small amounts, prefers email)
- Any combination across all 13 axes

---

### **2. Archetypes (Behavioral Signatures)**

**An archetype is a unique combination of dominant segments across axes.**

Think of it like a fingerprint:
```
Archetype #arch_880996 = "Premium Power Buyer"
├─ purchase_frequency: weekly_shopper
├─ purchase_value: high_value
├─ category_exploration: multi_category
├─ price_sensitivity: value_focused
├─ purchase_cadence: routine_buyer
├─ customer_maturity: established
├─ repurchase_behavior: loyal
├─ return_behavior: low_returner
├─ communication_preference: self_service
├─ problem_complexity_profile: simple_questions
├─ loyalty_trajectory: growing_engagement
├─ product_knowledge: expert_user
└─ value_sophistication: value_aware
```

**In database:**
- 93,564 customers actively segmented (customers with purchase history)
- 27,415 additional customer profiles (not yet segmented - no purchase history)
- Archetypes discovered dynamically based on unique behavioral combinations
- Each archetype typically has 5-500 members

**Why this matters for UI:**
- Show archetype name: "Premium Power Buyer"
- Show population: "Top 3.2% of customers"
- Show key traits: "Loyal, high-value, routine buyer"

---

### **3. Fuzzy Membership (The Math Part)**

**Key insight:** Customers don't perfectly fit into boxes. They belong to ALL segments with varying strength.

Example customer on `purchase_value` axis:
```
Segments for this axis:
├─ "high_value":        73% membership  ← Dominant
├─ "mid_tier":          22% membership
└─ "budget_conscious":   5% membership
```

**How to interpret:**
- This customer is MOSTLY high-value (73%)
- But has some mid-tier behavior (22%)
- Very little budget-conscious behavior (5%)

**Why fuzzy instead of hard clustering?**
- Customers are nuanced, not binary
- Someone can be "mostly loyal, but sometimes shops competitors"
- Allows for gray areas and transitions

**For frontend:** Display dominant segment boldly, show membership strength as confidence

---

### **4. Churn Risk Prediction**

**Definition:** Probability (0-100%) that customer will NOT make another purchase in next 30 days.

**Risk levels:**
- **Critical (70-100%):** Customer very likely to churn
- **High (50-70%):** At risk, needs intervention
- **Medium (30-50%):** Watch closely
- **Low (0-30%):** Healthy

**Calculated using:**
1. Days since last purchase (recency)
2. Average purchase frequency
3. LTV tier
4. Archetype patterns
5. Seasonal adjustments

**For frontend:**
- Use color coding (red/yellow/green)
- Show retention strategies
- Alert when critical customers open tickets

---

### **5. Lifetime Value (LTV)**

**Definition:** Total revenue generated by customer since first purchase.

**Tiers (relative to population):**
- **VIP:** Top 5% (e.g., $2000+)
- **High Value:** Top 20% (e.g., $500-$2000)
- **Standard:** Middle 60% (e.g., $100-$500)
- **Low:** Bottom 20% (e.g., <$100)

**For frontend:**
- Badge/label customers by tier
- Show LTV prominently in customer cards
- Use for prioritization (VIP tickets first)

---

## The Math Behind Behavioral Segmentation

### **Step 1: Feature Extraction**

For each customer, extract metrics from order history:

**Example for `purchase_frequency` axis:**
```python
features = {
    "total_purchases": 24,              # Count of orders
    "avg_days_between": 15.3,           # Average days between orders
    "purchase_velocity": 1.6,           # Orders per month
    "recency_days": 8,                  # Days since last order
    "frequency_trend": "increasing"     # Getting more frequent?
}
```

**13 axes × ~3-5 features each = ~40-50 features per customer**

Features are extracted differently based on axis type:
- **Purchase behavior axes** use order history data (dates, amounts, products)
- **Support behavior axes** use support ticket data (channels, complexity, resolution patterns)

---

### **Step 2: Clustering (Per Axis)**

For EACH axis independently:

**a) Normalize features:**
```python
# StandardScaler (zero mean, unit variance)
normalized_value = (raw_value - population_mean) / population_std

# Example:
# avg_days_between = 15.3
# population_mean = 45.0
# population_std = 20.0
# normalized = (15.3 - 45.0) / 20.0 = -1.49
# (This customer shops way more frequently than average)
```

**b) Find optimal number of clusters (k):**
```python
# Try k = 2, 3, 4, 5, 6
# For each k, calculate silhouette score (quality metric)
# Pick k with highest score (best separation)

# Silhouette score:
# 1.0 = perfect clusters (customers clearly grouped)
# 0.5 = good clusters
# 0.0 = overlapping clusters (bad)
```

**c) Run KMeans clustering:**
```python
from sklearn.cluster import KMeans

# Group customers into k clusters based on normalized features
kmeans = KMeans(n_clusters=optimal_k)
cluster_labels = kmeans.fit_predict(normalized_features)

# Result: Each customer assigned to one cluster
# Cluster 0 = "high_value" (73 customers)
# Cluster 1 = "mid_tier" (156 customers)
# Cluster 2 = "budget_conscious" (89 customers)
```

**d) Calculate fuzzy membership:**
```python
# Instead of hard assignment (customer IS cluster 0),
# calculate membership strength to ALL clusters

# Distance to each cluster center:
distances = {
    "high_value": 0.3,        # Close to this cluster
    "mid_tier": 1.2,          # Further away
    "budget_conscious": 2.8   # Very far
}

# Convert to membership using exponential decay:
# membership = exp(-distance²)

memberships = {
    "high_value":        exp(-0.3²) = 0.91  → 73%
    "mid_tier":          exp(-1.2²) = 0.30  → 22%
    "budget_conscious":  exp(-2.8²) = 0.001 → 5%
}
# (Normalized to sum to 100%)
```

**Result for ONE axis:**
- 3 segments discovered
- Each customer has membership scores to all 3
- Dominant segment = highest membership

---

### **Step 3: Multi-Axis Profiles**

Repeat Step 2 for ALL 13 axes:

```
Customer #C-12345:
├─ purchase_frequency
│  ├─ "weekly_shopper": 85%      ← Dominant
│  ├─ "occasional": 12%
│  └─ "once_yearly": 3%
├─ purchase_value
│  ├─ "high_value": 73%          ← Dominant
│  ├─ "mid_tier": 22%
│  └─ "budget": 5%
├─ category_exploration
│  ├─ "multi_category": 91%      ← Dominant
│  ├─ "category_loyal": 7%
│  └─ "experimenter": 2%
├─ communication_preference
│  ├─ "self_service": 78%        ← Dominant
│  ├─ "email_preferred": 18%
│  └─ "phone_caller": 4%
... (9 more axes)
```

**Dominant segments = Archetype signature**

---

### **Step 4: Archetype Discovery**

Group customers with SAME dominant segments:

```python
# Customers with this signature:
dominant_signature = {
    "purchase_frequency": "weekly_shopper",
    "purchase_value": "high_value",
    "category_exploration": "multi_category",
    "price_sensitivity": "value_focused",
    "purchase_cadence": "routine_buyer",
    "customer_maturity": "established",
    "repurchase_behavior": "loyal",
    "return_behavior": "low_returner",
    "communication_preference": "self_service",
    "problem_complexity_profile": "simple_questions",
    "loyalty_trajectory": "growing_engagement",
    "product_knowledge": "expert_user",
    "value_sophistication": "value_aware"
}

# Find all customers matching this signature → Archetype
archetype = {
    "archetype_id": "arch_880996",
    "member_count": 287,
    "population_percentage": 0.31,
    "avg_ltv": 3420.50,
    "dominant_segments": dominant_signature
}
```

**Result:**
- Archetypes discovered dynamically based on unique behavioral combinations
- Each represents a distinct behavioral pattern across 13 dimensions
- With 13 axes, potentially thousands of unique archetypes (though many are rare)
- Most archetypes have 5-500 members

---

### **Step 5: AI Naming (Claude API)**

Send archetype signature to Claude:

```python
prompt = f"""
You are a marketing analyst naming customer segments for an e-commerce business.

Behavioral signature:
- purchase_frequency: weekly_shopper (shops every 7-10 days)
- purchase_value: high_value (top 20% spenders)
- category_affinity: multi_category (buys across 4+ categories)
- price_sensitivity: value_focused (uses 15% off coupons)
- repurchase_inclination: loyal (85% return rate)

Generate:
1. A memorable 2-3 word segment name
2. A one-sentence description
"""

response = claude.generate(prompt)
# Returns: "Premium Power Buyer"
# "High-value, loyal customers who shop frequently across multiple categories"
```

**Stored in database for display**

---

## Data Structures

### **Customer Profile (Full Object)**

```typescript
interface CustomerProfile {
  customer_id: string;                    // "7827249201407"

  // Archetype (nullable for customers without purchase history)
  archetype: {
    archetype_id: string;                 // "arch_880996"
    dominant_segments: {
      [axis: string]: string;             // {purchase_value: "high_value", ...}
    };
    member_count: number;                 // 287
    population_percentage: number;        // 1.05
  } | null;                               // null = no orders yet, can't segment

  // Fuzzy memberships (advanced) - nullable
  fuzzy_memberships: {
    [axis: string]: {
      [segment: string]: number;          // {high_value: 0.73, mid_tier: 0.22}
    };
  } | null;                               // null = no segmentation data

  // Business metrics (always present, but may be 0 for new customers)
  business_metrics: {
    lifetime_value: number;               // 3420.50 (0 if no orders)
    total_orders: number;                 // 24 (0 if no orders)
    avg_order_value: number;              // 142.52 (0 if no orders)
    days_since_last_purchase: number;     // 8 (null if no orders)
    customer_tenure_days: number;         // 456
  };

  // Predictions (if requested) - only available for segmented customers
  churn_risk?: {
    risk_level: "critical" | "high" | "medium" | "low";
    churn_risk_score: number;             // 0.23 (23% chance of churn)
    factors: {
      recency_days: number;
      order_frequency: string;
      value_tier: string;
      engagement_trend: string;
    };
    recommendation: string;
  };
}
```

**Frontend Handling:**
```typescript
// Check if customer has been segmented
if (customer.archetype === null) {
  // Display: "New customer - awaiting first purchase to analyze behavior"
  return <NewCustomerBadge />;
}

// Customer has segments - safe to display
const dominantSegments = customer.archetype.dominant_segments;
```

---

### **Archetype Summary (List View)**

```typescript
interface ArchetypeSummary {
  archetype_id: string;                   // "arch_880996"
  segment_name: string;                   // "Premium Power Buyer" (AI-generated)
  description: string;                    // Human-readable interpretation

  // Population
  member_count: number;                   // 287
  population_percentage: number;          // 1.05

  // Metrics
  avg_lifetime_value: number;             // 3420.50
  total_revenue: number;                  // 981,683.50
  avg_orders: number;                     // 24
  churn_rate: number;                     // 0.12 (12%)

  // Signature (all 13 axes)
  dominant_segments: {
    // Purchase behavior (8 axes)
    purchase_frequency: string;           // "weekly_shopper"
    purchase_value: string;               // "high_value"
    category_exploration: string;         // "multi_category"
    price_sensitivity: string;            // "value_focused"
    purchase_cadence: string;             // "routine_buyer"
    customer_maturity: string;            // "established"
    repurchase_behavior: string;          // "loyal"
    return_behavior: string;              // "low_returner"
    // Support behavior (5 axes)
    communication_preference: string;     // "self_service"
    problem_complexity_profile: string;   // "simple_questions"
    loyalty_trajectory: string;           // "growing_engagement"
    product_knowledge: string;            // "expert_user"
    value_sophistication: string;         // "value_aware"
  };

  // Top traits (for display)
  key_traits: string[];                   // ["Loyal", "High-value", "Multi-category"]
}
```

---

### **Churn Risk (Individual)**

```typescript
interface ChurnRisk {
  customer_id: string;
  risk_level: "critical" | "high" | "medium" | "low";
  churn_risk_score: number;               // 0.0 - 1.0 (0% - 100%)

  factors: {
    recency_days: number;                 // Days since last purchase
    order_frequency: string;              // "weekly", "monthly", etc.
    value_tier: string;                   // "high_value", "mid_tier", etc.
    engagement_trend: string;             // "increasing", "stable", "declining"
  };

  recommendation: string;                 // AI-generated retention strategy
}
```

---

### **Churn Aggregate (Population)**

```typescript
interface ChurnAggregate {
  total_customers: number;                // 27415
  sample_size: number;                    // 1000 (sampled for performance)

  churn_risk_distribution: {
    critical: {
      count: number;                      // In sample
      percentage: number;                 // Of sample
      estimated_total: number;            // Extrapolated to full population
    };
    high: { ... };
    medium: { ... };
    low: { ... };
  };

  estimated_churn_30_days: number;        // Predicted customers lost
  estimated_churn_90_days: number;

  note: string;                           // Methodology explanation
}
```

---

## Complete API Reference

**Base URL:** `https://ecommerce-backend-production-b9cc.up.railway.app`

**Authentication:** `X-API-Key: <your-key>` (header)

---

### **1. Health & Status**

#### `GET /health`

Check system status and data availability.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-12T...",
  "data_status": {
    "customers_loaded": 27415,
    "archetypes_available": 868
  }
}
```

---

### **2. Customer Endpoints**

#### `GET /api/mcp/customer/random`

Get random customer profile (for testing/exploration).

**Response:** Full `CustomerProfile` object

**Use case:**
- Testing frontend components
- Exploring data
- Demos

---

#### `GET /api/mcp/customer/{customer_id}`

Get specific customer's profile.

**Path params:**
- `customer_id` (string): Shopify customer ID

**Response:** Full `CustomerProfile` object

**Status codes:**
- 200: Customer found
- 404: Customer not found
- 500: Error

**Use case:**
- Customer 360 view
- Support ticket sidebar
- Campaign targeting

---

#### `GET /api/mcp/customer/{customer_id}/orders`

Get customer's order history from Shopify.

**Path params:**
- `customer_id` (string): Shopify customer ID

**Query params:**
- `search_terms` (optional): Comma-separated search terms
- `start_date` (optional): ISO date (YYYY-MM-DD)
- `end_date` (optional): ISO date

**Response:**
```json
{
  "customer_id": "7827249201407",
  "orders": [
    {
      "order_id": "87265",
      "order_number": "#87265",
      "created_at": "2024-08-29T10:30:00Z",
      "total_price": "18.69",
      "line_items": [
        {
          "title": "478 Rose Signature Cotton Thread",
          "vendor": "American & Efird Signature",
          "quantity": 1,
          "price": "18.69"
        }
      ],
      "tracking_numbers": ["1Z999AA10123456784"],
      "fulfillment_status": "fulfilled"
    }
  ],
  "total_orders": 24,
  "total_spent": "3420.50"
}
```

**Use case:**
- Support agents answering "did I order X?"
- Order history display
- Product recommendation context

---

#### `GET /api/mcp/customer/{customer_id}/churn-risk`

Predict churn risk for specific customer.

**Response:** `ChurnRisk` object

**Use case:**
- Alert agents when at-risk customer contacts support
- Prioritize retention campaigns
- Display risk indicator in customer cards

---

### **3. Archetype Endpoints**

#### `GET /api/mcp/archetypes/top`

Get top archetypes by metric.

**Query params:**
- `metric` (optional): `total_ltv`, `avg_ltv`, `member_count` (default: `total_ltv`)
- `limit` (optional): Number of results (default: 10)

**Response:**
```json
{
  "archetypes": [
    {
      "archetype_id": "arch_880996",
      "segment_name": "Premium Power Buyer",
      "member_count": 287,
      "population_percentage": 1.05,
      "avg_ltv": 3420.50,
      "total_ltv": 981683.50,
      "dominant_segments": { ... }
    }
  ],
  "metric": "total_ltv",
  "total_archetypes": 868
}
```

**Use case:**
- Dashboard "Top Segments" widget
- Campaign target selection
- Business intelligence

---

#### `GET /api/mcp/archetypes/{archetype_id}`

Get detailed stats for specific archetype.

**Response:**
```json
{
  "archetype_id": "arch_880996",
  "segment_name": "Premium Power Buyer",
  "description": "High-value loyal customers...",
  "member_count": 287,
  "population_percentage": 1.05,

  "metrics": {
    "avg_ltv": 3420.50,
    "total_ltv": 981683.50,
    "avg_orders": 24,
    "avg_order_value": 142.52,
    "churn_rate": 0.12
  },

  "dominant_segments": { ... },
  "key_traits": ["Loyal", "High-value", "Multi-category"]
}
```

**Use case:**
- Archetype detail page
- Segment comparison
- Marketing strategy planning

---

### **4. Analytics Endpoints**

#### `GET /api/mcp/churn/aggregate`

Aggregate churn analysis across customer base.

**Response:** `ChurnAggregate` object

**Use case:**
- Executive dashboard
- Retention strategy planning
- Forecasting

---

#### `GET /api/mcp/growth/projection`

Project customer base growth.

**Query params:**
- `months` (optional): Forecast horizon (default: 12)

**Response:**
```json
{
  "current_customers": 27415,
  "projections": {
    "monthly": [
      {
        "month": "2025-12",
        "estimated_customers": 28150,
        "growth_rate": 0.027,
        "new_customers": 735
      }
    ],
    "quarterly": [ ... ],
    "yearly": [ ... ]
  },
  "assumptions": {
    "monthly_churn_rate": 0.05,
    "monthly_acquisition_rate": 0.08
  }
}
```

**Use case:**
- Growth forecasting dashboard
- Investor reports
- Capacity planning

---

#### `GET /api/mcp/archetypes/growth-projection`

Project archetype distribution over time.

**Query params:**
- `months` (optional): Forecast horizon (default: 12)

**Response:**
```json
{
  "current_distribution": {
    "arch_880996": {
      "member_count": 287,
      "percentage": 1.05
    }
  },
  "projected_distribution": {
    "2025-12": {
      "arch_880996": {
        "member_count": 294,
        "percentage": 1.04
      }
    }
  }
}
```

**Use case:**
- Segment trends analysis
- Campaign planning
- Product strategy

---

### **5. Natural Language Query**

#### `POST /api/mcp/query/natural-language`

Query using plain English (powered by Claude AI).

**Query params:**
- `query` (string): Natural language question

**Examples:**
```
"Show me customers at risk of churning"
"What's our revenue from Premium Power Buyers?"
"Which archetypes have highest LTV?"
"How many customers bought in the last 30 days?"
```

**Response:**
```json
{
  "query": "Show me customers at risk of churning",
  "interpretation": "Analyzing customers with high churn risk...",
  "results": {
    "customers": [ ... ],
    "count": 234,
    "total_ltv_at_risk": 125430.50
  },
  "visualization_hint": "customer_list",
  "tool_used": "analyze_customers"
}
```

**Use case:**
- Analytics search bar
- Executive queries
- Conversational BI

---

### **6. Campaign Endpoints**

#### `POST /api/campaigns/create`

Create targeted campaign.

**Request body:**
```json
{
  "goal": "retention",              // retention, winback, growth, loyalty
  "name": "Holiday VIP Campaign",
  "channel": "email",               // email, sms

  "target_audience": {
    "archetype_ids": ["arch_880996"],
    "ltv_min": 1000,
    "churn_risk_min": 0.5,
    "churn_risk_max": 0.9
  },

  "content": {
    "subject": "Exclusive Holiday Preview",
    "body": "Hi {{first_name}}, ..."
  },

  "schedule": {
    "send_at": "2025-12-15T10:00:00Z",
    "timezone": "America/New_York"
  }
}
```

**Response:**
```json
{
  "campaign_id": "camp_123456",
  "estimated_reach": 234,
  "predicted_open_rate": 0.42,
  "predicted_conversion_rate": 0.18,
  "predicted_revenue": 15230.50,
  "status": "scheduled"
}
```

**Use case:**
- Campaign builder
- Automated retention
- Marketing automation

---

### **7. Support Integration**

#### `POST /api/gorgias/webhook`

Webhook endpoint for Gorgias tickets.

**Headers:**
- `X-Webhook-Token`: Shared secret for authentication

**Request body:** Gorgias webhook payload

**Process:**
1. Extract customer from ticket
2. Fetch customer profile + churn risk
3. Query order history if needed
4. Generate AI response draft
5. Post to Gorgias as internal note + draft reply

**Response:**
```json
{
  "status": "accepted",
  "ticket_id": 235766516,
  "message": "Webhook received and queued for processing"
}
```

**Processing time:** ~7-10 seconds async

**Use case:**
- Automated support intelligence
- Agent assistance
- VIP identification

---

## Common Use Cases

### **Use Case 1: Agent Inbox with Customer Intelligence**

**Frontend needs:**
1. When ticket opens, fetch customer profile
2. Display prominently:
   - LTV (with tier badge)
   - Churn risk (with color coding)
   - Archetype name
   - Order count
3. If churn risk > 70%, show alert
4. Show AI-generated draft response

**API calls:**
```typescript
// 1. Get customer profile
const profile = await fetch(
  `/api/mcp/customer/${customerId}`,
  { headers: { 'X-API-Key': apiKey } }
);

// 2. Get churn risk (if not in profile)
const churn = await fetch(
  `/api/mcp/customer/${customerId}/churn-risk`,
  { headers: { 'X-API-Key': apiKey } }
);

// 3. Display in sidebar:
{profile.business_metrics.lifetime_value > 2000 && <VIPBadge />}
{churn.risk_level === 'critical' && <ChurnAlert />}
```

---

### **Use Case 2: Analytics Dashboard**

**Frontend needs:**
1. Top archetypes by revenue
2. Churn risk distribution (pie chart)
3. Growth projection (line chart)
4. Recent customer activity

**API calls:**
```typescript
// 1. Top archetypes
const topArchetypes = await fetch(
  '/api/mcp/archetypes/top?metric=total_ltv&limit=10'
);

// 2. Churn distribution
const churnStats = await fetch('/api/mcp/churn/aggregate');

// 3. Growth forecast
const growth = await fetch('/api/mcp/growth/projection?months=12');

// Render charts with data
```

---

### **Use Case 3: Campaign Builder**

**Frontend workflow:**
1. User selects goal: "Retention"
2. System recommends target archetypes (high churn risk + high LTV)
3. User customizes filters
4. Preview audience size
5. Compose email with AI assistance
6. Schedule campaign

**API calls:**
```typescript
// 1. Get suggested archetypes for retention
const archetypes = await fetch(
  '/api/mcp/archetypes/top?metric=total_ltv&limit=20'
);

// Filter by churn risk client-side or:
const churnStats = await fetch('/api/mcp/churn/aggregate');

// 2. Preview audience size
const preview = await fetch('/api/campaigns/preview', {
  method: 'POST',
  body: JSON.stringify({
    archetype_ids: ['arch_880996'],
    churn_risk_min: 0.5
  })
});

// 3. Create campaign
const campaign = await fetch('/api/campaigns/create', {
  method: 'POST',
  body: JSON.stringify(campaignData)
});
```

---

### **Use Case 4: Customer 360 View**

**Frontend layout:**
```
┌─────────────────────────────────────────┐
│ Customer: Sarah Johnson                 │
│ sarah.j@email.com                       │
│                                         │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│ │ $3,420  │ │ 28      │ │ ⚠️ 73%   │   │
│ │ LTV     │ │ Orders  │ │ Churn   │   │
│ └─────────┘ └─────────┘ └─────────┘   │
│                                         │
│ 🎯 Archetype: Premium Power Buyer       │
│    Top 3.2% • 287 similar customers     │
│                                         │
│ Behavioral Traits:                      │
│ • Loyal (85% return rate)               │
│ • High-value (95th percentile)          │
│ • Multi-category shopper                │
│                                         │
│ ⚠️ RETENTION ALERT                      │
│ Customer is at high churn risk.         │
│ Last purchase: 18 days ago              │
│ (Usually buys every 24 days)            │
│                                         │
│ Recommended Actions:                    │
│ • Offer 20% discount                    │
│ • Expedite current order (free)         │
│ • Send personalized product recs        │
│                                         │
│ [View Order History]                    │
│ [Create Retention Campaign]             │
└─────────────────────────────────────────┘
```

**API calls:**
```typescript
const customer = await fetch(`/api/mcp/customer/${id}`);
const orders = await fetch(`/api/mcp/customer/${id}/orders`);
const churn = customer.churn_risk; // Included in profile
```

---

## Frontend Integration Examples

### **React Hook for Customer Data**

```typescript
import { useState, useEffect } from 'react';

interface UseCustomerOptions {
  customerId: string;
  includeOrders?: boolean;
  includeChurn?: boolean;
}

export function useCustomer({
  customerId,
  includeOrders = false,
  includeChurn = true
}: UseCustomerOptions) {
  const [customer, setCustomer] = useState(null);
  const [orders, setOrders] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchCustomer() {
      try {
        setLoading(true);

        // Fetch customer profile
        const profileRes = await fetch(
          `${API_BASE}/api/mcp/customer/${customerId}`,
          { headers: { 'X-API-Key': API_KEY } }
        );
        const profile = await profileRes.json();

        // Optionally fetch orders
        if (includeOrders) {
          const ordersRes = await fetch(
            `${API_BASE}/api/mcp/customer/${customerId}/orders`
          );
          const ordersData = await ordersRes.json();
          setOrders(ordersData);
        }

        setCustomer(profile);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }

    fetchCustomer();
  }, [customerId, includeOrders]);

  return { customer, orders, loading, error };
}

// Usage:
function CustomerCard({ customerId }) {
  const { customer, loading, error } = useCustomer({ customerId });

  if (loading) return <Spinner />;
  if (error) return <Error message={error.message} />;

  return (
    <Card>
      <h2>{customer.customer_id}</h2>
      <Badge>LTV: ${customer.business_metrics.lifetime_value}</Badge>
      {customer.churn_risk?.risk_level === 'critical' && (
        <Alert variant="danger">
          High churn risk: {customer.churn_risk.churn_risk_score}%
        </Alert>
      )}
      <ArchetypeBadge archetype={customer.archetype} />
    </Card>
  );
}
```

---

### **Churn Risk Color Coding**

```typescript
export function getChurnRiskColor(riskLevel: string): string {
  switch (riskLevel) {
    case 'critical': return '#DC2626'; // red-600
    case 'high':     return '#F59E0B'; // amber-500
    case 'medium':   return '#3B82F6'; // blue-500
    case 'low':      return '#10B981'; // green-500
    default:         return '#6B7280'; // gray-500
  }
}

export function ChurnRiskBadge({ churnRisk }) {
  const color = getChurnRiskColor(churnRisk.risk_level);
  const percentage = Math.round(churnRisk.churn_risk_score * 100);

  return (
    <div style={{
      backgroundColor: color,
      color: 'white',
      padding: '4px 12px',
      borderRadius: '12px',
      fontSize: '14px',
      fontWeight: 600
    }}>
      ⚠️ {percentage}% Churn Risk
    </div>
  );
}
```

---

### **LTV Tier Badge**

```typescript
export function getLTVTier(ltv: number): {
  tier: string;
  color: string;
  label: string;
} {
  if (ltv >= 2000) return {
    tier: 'vip',
    color: '#7C3AED', // purple
    label: 'VIP'
  };
  if (ltv >= 500) return {
    tier: 'high',
    color: '#2563EB', // blue
    label: 'High Value'
  };
  if (ltv >= 100) return {
    tier: 'standard',
    color: '#059669', // green
    label: 'Standard'
  };
  return {
    tier: 'low',
    color: '#6B7280', // gray
    label: 'Low Value'
  };
}

export function LTVBadge({ ltv }) {
  const { color, label } = getLTVTier(ltv);

  return (
    <div style={{
      backgroundColor: color,
      color: 'white',
      padding: '4px 12px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: 600
    }}>
      💎 {label} • ${ltv.toFixed(2)}
    </div>
  );
}
```

---

### **Archetype Display**

```typescript
export function ArchetypeCard({ archetype }) {
  return (
    <div className="archetype-card">
      <h3>{archetype.segment_name || archetype.archetype_id}</h3>

      <div className="stats">
        <span>{archetype.member_count} customers</span>
        <span>Top {archetype.population_percentage.toFixed(1)}%</span>
      </div>

      <div className="traits">
        {Object.entries(archetype.dominant_segments).map(([axis, segment]) => (
          <span key={axis} className="trait-badge">
            {segment.replace(/_/g, ' ')}
          </span>
        ))}
      </div>

      <div className="metrics">
        <div>Avg LTV: ${archetype.avg_ltv?.toFixed(2)}</div>
        <div>Avg Orders: {archetype.avg_orders}</div>
      </div>
    </div>
  );
}
```

---

## Summary for Frontend Developers

### **What You Need to Know:**

1. **Behavioral segmentation** = customers grouped by BEHAVIOR, not demographics
2. **13 axes** = 13 independent dimensions of shopping behavior (8 purchase + 5 support)
3. **Archetypes** = unique combinations of dominant segments across axes
4. **Fuzzy membership** = customers belong to ALL segments with varying strength
5. **Churn risk** = probability of not purchasing again (0-100%)
6. **LTV** = total revenue from customer lifetime
7. **Null handling** = 22.7% of customers don't have segments yet (no order history)

### **Key API Endpoints:**

- `GET /api/mcp/customer/{id}` - Full customer profile
- `GET /api/mcp/customer/{id}/orders` - Order history
- `GET /api/mcp/archetypes/top` - Top segments
- `GET /api/mcp/churn/aggregate` - Population churn
- `POST /api/mcp/query/natural-language` - AI queries

### **UI Priorities:**

1. **Always show:** LTV, churn risk, archetype name
2. **Color code:** Churn risk (red/yellow/green), LTV tiers
3. **Alert on:** Critical churn risk (70%+)
4. **Emphasize:** VIP customers, at-risk high-value customers

### **Next Steps:**

See complete API examples in:
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - Full endpoint reference
- [VERTICAL_CRM_VISION.md](VERTICAL_CRM_VISION.md) - UI mockups and workflows

---

**Questions?** Reference the backend code:
- Clustering engine: `backend/segmentation/ecommerce_clustering_engine.py`
- Feature extraction: `backend/segmentation/ecommerce_feature_extraction.py`
- API routers: `backend/api/routers/`

---

**Status:** Complete backend reference for frontend development
**Last Updated:** 2025-11-12
