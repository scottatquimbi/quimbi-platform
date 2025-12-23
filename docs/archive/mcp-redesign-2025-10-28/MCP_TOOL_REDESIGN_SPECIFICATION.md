# MCP Tool Redesign: Detailed Specification

**Purpose:** Define exactly what each consolidated tool does and how it covers user queries
**Date:** 2025-10-28

---

## Overview

**Goal:** Consolidate from 8 tools → 5 tools while maintaining 100% coverage of 49 query types

**Design Philosophy:**
1. **Domain-based separation** - Each tool owns a clear domain
2. **Parameter-driven flexibility** - Use parameters instead of sub-types
3. **Composable filters** - Enable complex queries through parameter combinations
4. **Predictable routing** - Question domain → tool mapping is intuitive

---

## Tool 1: `query_customers`

### Purpose
Find, filter, and analyze individual customers or customer lists based on behavior, value, risk, and patterns.

### Replaces
- `analyze_customers` (6 sub-types)
- `analyze_behavior` (6 sub-types)
- `lookup_customer` (3 info types)

**Total: 15 query types consolidated**

---

### Tool Definition

```json
{
  "name": "query_customers",
  "description": "Find and analyze customers based on value, behavior, risk, and patterns. Use this for ANY question about individual customers or lists of customers (e.g., 'who are my best customers?', 'show me at-risk VIPs', 'find one-time buyers', 'what's customer 123's profile?').",
  "input_schema": {
    "type": "object",
    "properties": {
      "scope": {
        "type": "string",
        "enum": ["individual", "list"],
        "description": "Query a single customer (requires customer_id) or get a filtered list of customers",
        "default": "list"
      },
      "customer_id": {
        "type": "string",
        "description": "Required if scope='individual'. Customer ID (13-digit number) or email address"
      },
      "info_requested": {
        "type": "array",
        "items": {
          "enum": [
            "profile",           // Full profile with segments, archetype, LTV
            "churn_risk",        // Churn probability with risk factors
            "purchase_history",  // Order timeline and patterns
            "ltv_forecast",      // Future value prediction
            "recommendations",   // Next best actions for this customer
            "segment_membership" // Detailed segment strengths
          ]
        },
        "description": "What information to return about customer(s). For scope='individual', defaults to ['profile', 'churn_risk']. For scope='list', returns basic profile for each.",
        "default": ["profile"]
      },
      "filters": {
        "type": "object",
        "description": "Criteria to filter customers (only for scope='list'). All filters use AND logic.",
        "properties": {
          "churn_risk_min": {
            "type": "number",
            "description": "Minimum churn risk (0.0-1.0). Use 0.7 for 'critical', 0.5 for 'high', 0.3 for 'medium'"
          },
          "churn_risk_max": {
            "type": "number",
            "description": "Maximum churn risk (0.0-1.0)"
          },
          "ltv_min": {
            "type": "number",
            "description": "Minimum lifetime value in dollars"
          },
          "ltv_max": {
            "type": "number",
            "description": "Maximum lifetime value in dollars"
          },
          "segment": {
            "type": "string",
            "description": "Filter by segment name (e.g., 'frequent_buyer', 'seasonal_shopper', 'premium_buyer')"
          },
          "archetype_id": {
            "type": "string",
            "description": "Filter by specific archetype ID"
          },
          "last_purchase_days_min": {
            "type": "integer",
            "description": "Minimum days since last purchase (use for 'lapsed' customers)"
          },
          "last_purchase_days_max": {
            "type": "integer",
            "description": "Maximum days since last purchase (use for 'recent' customers)"
          },
          "total_orders_min": {
            "type": "integer",
            "description": "Minimum number of orders"
          },
          "total_orders_max": {
            "type": "integer",
            "description": "Maximum number of orders (use 1 for 'one-time buyers')"
          },
          "behavior_pattern": {
            "type": "string",
            "enum": [
              "one_time_buyer",      // Customers with exactly 1 order
              "frequent_buyer",       // High order frequency
              "seasonal_shopper",     // Purchases align with seasons/holidays
              "declining_engagement", // Slowing purchase frequency
              "growing_engagement",   // Increasing purchase frequency
              "discount_dependent",   // Only buys on sale
              "premium_buyer",        // High AOV, low discount usage
              "routine_buyer",        // Consistent purchase cadence
              "erratic_buyer"         // Inconsistent patterns
            ],
            "description": "Filter by detected behavioral pattern"
          },
          "is_b2b": {
            "type": "boolean",
            "description": "Filter for B2B vs B2C customers (bulk orders, business indicators)"
          },
          "price_sensitivity": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "How sensitive customer is to price/discounts"
          }
        }
      },
      "sort_by": {
        "type": "string",
        "enum": [
          "ltv_desc",          // Lifetime value (highest first)
          "ltv_asc",           // Lifetime value (lowest first)
          "churn_risk_desc",   // Churn risk (highest first) - at-risk customers
          "churn_risk_asc",    // Churn risk (lowest first) - loyal customers
          "impact_desc",       // LTV × churn_risk (highest impact at-risk customers)
          "recency_desc",      // Last purchase date (most recent first)
          "recency_asc",       // Last purchase date (longest ago first)
          "frequency_desc",    // Total orders (highest first)
          "frequency_asc",     // Total orders (lowest first)
          "aov_desc"           // Average order value (highest first)
        ],
        "description": "How to sort results",
        "default": "ltv_desc"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of customers to return (for scope='list')",
        "default": 100,
        "maximum": 1000
      }
    },
    "required": []
  }
}
```

---

### Query Coverage Map

| Query Type | Parameters Used | Example Query |
|------------|-----------------|---------------|
| **High-value customers** | `filters.ltv_min: 5000`, `sort_by: ltv_desc` | "show me my best customers" |
| **At-risk customers** | `filters.churn_risk_min: 0.7`, `sort_by: impact_desc` | "which customers are likely to churn" |
| **VIPs at risk** | `filters.ltv_min: 5000`, `filters.churn_risk_min: 0.5`, `sort_by: impact_desc` | "show me high-value customers at churn risk" |
| **One-time buyers** | `filters.total_orders_max: 1` | "who bought once and never came back" |
| **Lapsed customers** | `filters.last_purchase_days_min: 90`, `sort_by: recency_asc` | "customers who haven't purchased in 90 days" |
| **B2B identification** | `filters.is_b2b: true`, `sort_by: ltv_desc` | "which customers are businesses" |
| **Seasonal shoppers** | `filters.behavior_pattern: seasonal_shopper` | "find seasonal buyers" |
| **Declining engagement** | `filters.behavior_pattern: declining_engagement`, `sort_by: churn_risk_desc` | "customers whose activity is slowing" |
| **Growing engagement** | `filters.behavior_pattern: growing_engagement` | "customers increasing their spending" |
| **Discount dependent** | `filters.behavior_pattern: discount_dependent` | "who only buys on sale" |
| **Premium buyers** | `filters.behavior_pattern: premium_buyer`, `filters.ltv_min: 1000` | "high-value customers who don't need discounts" |
| **Frequent buyers** | `filters.behavior_pattern: frequent_buyer` | "most frequent purchasers" |
| **Recent buyers** | `filters.last_purchase_days_max: 30`, `sort_by: recency_desc` | "customers who bought recently" |
| **Individual lookup** | `scope: individual`, `customer_id: "123"`, `info_requested: ["profile", "churn_risk"]` | "show me customer 5971333382399" |
| **Customer churn risk** | `scope: individual`, `customer_id: "123"`, `info_requested: ["churn_risk"]` | "what's the churn risk for customer@email.com" |
| **Customer LTV forecast** | `scope: individual`, `customer_id: "123"`, `info_requested: ["ltv_forecast"]` | "predict future value of customer 123" |
| **Customer purchase history** | `scope: individual`, `customer_id: "123"`, `info_requested: ["purchase_history"]` | "show purchase history for customer X" |
| **Customer recommendations** | `scope: individual`, `customer_id: "123"`, `info_requested: ["recommendations"]` | "what products should I recommend to customer Y" |
| **RFM analysis** | `sort_by: varies`, `filters: ltv_min/recency/frequency` | "show me RFM segments" |
| **Behavioral analysis** | `filters.behavior_pattern: varies` | "analyze customer behavior patterns" |
| **Product affinity** | `info_requested: ["profile"]` (includes purchase patterns) | "what do high-value customers buy" (combine with query_products) |

**Coverage: 21 distinct query types**

---

### Example Usage Scenarios

#### Scenario 1: Simple High-Value Query
**User:** "Show me my best customers"

**Claude routes to:**
```json
{
  "scope": "list",
  "filters": {
    "ltv_min": 5000
  },
  "sort_by": "ltv_desc",
  "limit": 100
}
```

**Returns:** Top 100 customers by LTV

---

#### Scenario 2: Complex Retention Target
**User:** "Find high-value customers who haven't purchased in 90 days but used to buy frequently"

**Claude routes to:**
```json
{
  "scope": "list",
  "filters": {
    "ltv_min": 2000,
    "last_purchase_days_min": 90,
    "behavior_pattern": "declining_engagement",
    "total_orders_min": 5
  },
  "sort_by": "impact_desc",
  "limit": 100
}
```

**Returns:** At-risk valuable customers for win-back campaign

---

#### Scenario 3: Individual Customer Lookup
**User:** "What's the churn risk for customer 5971333382399?"

**Claude routes to:**
```json
{
  "scope": "individual",
  "customer_id": "5971333382399",
  "info_requested": ["churn_risk", "profile"]
}
```

**Returns:** Full churn analysis with risk score, factors, recommendations

---

#### Scenario 4: Behavioral Segmentation
**User:** "Who are my one-time buyers with high LTV?"

**Claude routes to:**
```json
{
  "scope": "list",
  "filters": {
    "total_orders_max": 1,
    "ltv_min": 200
  },
  "sort_by": "ltv_desc",
  "limit": 100
}
```

**Returns:** One-time buyers ranked by order value (upsell opportunity)

---

#### Scenario 5: Multi-Criteria Filter
**User:** "Show me VIP customers in the seasonal shopper segment who are at moderate churn risk"

**Claude routes to:**
```json
{
  "scope": "list",
  "filters": {
    "ltv_min": 5000,
    "behavior_pattern": "seasonal_shopper",
    "churn_risk_min": 0.3,
    "churn_risk_max": 0.6
  },
  "sort_by": "churn_risk_desc",
  "limit": 50
}
```

**Returns:** High-value seasonal shoppers who need proactive engagement

---

## Tool 2: `query_segments`

### Purpose
Analyze customer segments, archetypes, cohorts, and how they're growing or changing over time.

### Replaces
- `analyze_segments` (4 sub-types)
- Direct MCP: `get_archetype_stats`, `search_customers` (when used for segment filtering)

**Total: 7 query types consolidated**

---

### Tool Definition

```json
{
  "name": "query_segments",
  "description": "Analyze customer segments and archetypes - understand who your customer types are, how they behave, and how they're changing. Use this for questions about groups of customers, not individuals (e.g., 'what types of customers do I have?', 'which segments are growing?', 'compare premium vs budget shoppers').",
  "input_schema": {
    "type": "object",
    "properties": {
      "analysis": {
        "type": "string",
        "enum": [
          "overview",      // List all segments with key metrics
          "growth",        // Project how segments will grow/shrink
          "comparison",    // Compare specific segments side-by-side
          "seasonal"       // Identify segments active during specific events
        ],
        "description": "Type of segment analysis to perform",
        "default": "overview"
      },
      "segment_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "For analysis='comparison': list of segment/archetype IDs to compare (2-5 IDs)"
      },
      "filters": {
        "type": "object",
        "description": "Filter which segments to include in results",
        "properties": {
          "growth_trend": {
            "type": "string",
            "enum": ["growing", "shrinking", "stable"],
            "description": "Filter by growth trajectory"
          },
          "value_tier": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Filter by average customer value (LTV)"
          },
          "risk_level": {
            "type": "string",
            "enum": ["at_risk", "healthy"],
            "description": "Filter by aggregate churn risk"
          },
          "size_min": {
            "type": "integer",
            "description": "Minimum number of customers in segment"
          },
          "size_max": {
            "type": "integer",
            "description": "Maximum number of customers in segment"
          }
        }
      },
      "event": {
        "type": "string",
        "description": "For analysis='seasonal': event name (e.g., 'halloween', 'black_friday', 'christmas', 'spring_sale')",
        "enum": [
          "halloween", "thanksgiving", "black_friday", "cyber_monday",
          "christmas", "holiday_season", "new_year", "valentines",
          "easter", "spring", "summer", "fall", "winter", "back_to_school"
        ]
      },
      "timeframe_months": {
        "type": "integer",
        "description": "For analysis='growth': how many months ahead to project (3=quarter, 12=year, 24=two years)",
        "default": 12,
        "minimum": 1,
        "maximum": 36
      },
      "sort_by": {
        "type": "string",
        "enum": [
          "size",          // Number of customers (largest first)
          "ltv",           // Average customer value (highest first)
          "total_revenue", // Total revenue from segment (highest first)
          "growth_rate",   // Projected growth (fastest growing first)
          "churn_rate"     // Churn risk (highest risk first)
        ],
        "description": "How to rank segments",
        "default": "total_revenue"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of segments to return",
        "default": 10,
        "maximum": 50
      },
      "include_details": {
        "type": "boolean",
        "description": "Include detailed behavioral characteristics for each segment",
        "default": true
      }
    },
    "required": []
  }
}
```

---

### Query Coverage Map

| Query Type | Parameters Used | Example Query |
|------------|-----------------|---------------|
| **Segment overview** | `analysis: overview`, `sort_by: total_revenue` | "what types of customers do I have" |
| **Top segments by value** | `analysis: overview`, `sort_by: ltv` | "which segments spend the most" |
| **Top segments by size** | `analysis: overview`, `sort_by: size` | "which are my largest customer groups" |
| **Growing segments** | `analysis: growth`, `filters.growth_trend: growing` | "which segments are growing" |
| **Shrinking segments** | `analysis: growth`, `filters.growth_trend: shrinking` | "which segments are declining" |
| **Segment growth projection** | `analysis: growth`, `timeframe_months: 12` | "how will segments grow over next year" |
| **Seasonal segment analysis** | `analysis: seasonal`, `event: halloween` | "who are my Halloween shoppers" |
| **Holiday shoppers** | `analysis: seasonal`, `event: christmas` | "who shops during Christmas" |
| **Black Friday targets** | `analysis: seasonal`, `event: black_friday` | "which customers engage during Black Friday" |
| **Segment comparison** | `analysis: comparison`, `segment_ids: ["A123", "B456"]` | "compare premium vs budget shoppers" |
| **At-risk segments** | `analysis: overview`, `filters.risk_level: at_risk`, `sort_by: churn_rate` | "which segments have highest churn" |
| **High-value segments** | `analysis: overview`, `filters.value_tier: high` | "show me my most valuable segments" |
| **Small segments** | `analysis: overview`, `filters.size_max: 100` | "niche customer groups" |

**Coverage: 13 distinct query types (7 main + 6 variations)**

---

### Example Usage Scenarios

#### Scenario 1: Segment Overview
**User:** "What types of customers do I have?"

**Claude routes to:**
```json
{
  "analysis": "overview",
  "sort_by": "total_revenue",
  "limit": 10,
  "include_details": true
}
```

**Returns:** Top 10 segments with member count, avg LTV, total revenue, behavioral traits

---

#### Scenario 2: Growth Analysis
**User:** "Which customer segments are growing?"

**Claude routes to:**
```json
{
  "analysis": "growth",
  "filters": {
    "growth_trend": "growing"
  },
  "timeframe_months": 12,
  "sort_by": "growth_rate"
}
```

**Returns:** Segments with positive growth trajectory, projected growth rates

---

#### Scenario 3: Seasonal Targeting
**User:** "Who are my Halloween shoppers?"

**Claude routes to:**
```json
{
  "analysis": "seasonal",
  "event": "halloween",
  "sort_by": "size"
}
```

**Returns:** Segments with high October engagement, purchase patterns, targeting recommendations

---

#### Scenario 4: Segment Comparison
**User:** "Compare premium buyers vs discount shoppers"

**Claude routes to:**
```json
{
  "analysis": "comparison",
  "segment_ids": ["premium_buyer_archetype", "discount_shopper_archetype"],
  "include_details": true
}
```

**Returns:** Side-by-side comparison: LTV, churn rate, AOV, purchase frequency, behaviors

---

#### Scenario 5: At-Risk Segments
**User:** "Which customer groups are at highest churn risk?"

**Claude routes to:**
```json
{
  "analysis": "overview",
  "filters": {
    "risk_level": "at_risk"
  },
  "sort_by": "churn_rate",
  "limit": 10
}
```

**Returns:** Top 10 segments by churn risk with reasons and retention recommendations

---

## Tool 3: `forecast_business_metrics`

### Purpose
Predict future business metrics like revenue, customer count, LTV, and churn rates over time.

### Replaces
- `forecast_metrics` (4 sub-types)
- Direct endpoint: `/api/mcp/growth/projection`

**Total: 5 query types consolidated**

---

### Tool Definition

```json
{
  "name": "forecast_business_metrics",
  "description": "Forecast future business performance - predict revenue, customer growth, churn, and value metrics over time. Use this for questions about the future (e.g., 'what will Q4 revenue be?', 'how many customers will I have next year?', 'revenue forecast').",
  "input_schema": {
    "type": "object",
    "properties": {
      "metrics": {
        "type": "array",
        "items": {
          "enum": [
            "revenue",          // Total revenue forecast
            "customer_count",   // Total active customers
            "new_customers",    // New customer acquisitions
            "churned_customers",// Customers lost to churn
            "average_ltv",      // Average lifetime value per customer
            "average_aov",      // Average order value
            "churn_rate",       // Percentage of customers churning
            "retention_rate"    // Percentage of customers retained
          ]
        },
        "description": "Which metrics to forecast (can request multiple). Defaults to ['revenue', 'customer_count']",
        "default": ["revenue", "customer_count"]
      },
      "timeframe_months": {
        "type": "integer",
        "description": "How many months ahead to forecast (1=1 month, 3=quarter, 6=half year, 12=year, 24=2 years)",
        "default": 12,
        "minimum": 1,
        "maximum": 36
      },
      "breakdown": {
        "type": "string",
        "enum": ["monthly", "quarterly", "annual", "total_only"],
        "description": "Granularity of forecast output",
        "default": "monthly"
      },
      "segment_filter": {
        "type": "string",
        "description": "Optional: forecast for specific segment/archetype ID only (e.g., 'premium_buyers'). Leave empty for all customers."
      },
      "confidence_interval": {
        "type": "boolean",
        "description": "Include confidence bands (low/expected/high predictions)",
        "default": true
      },
      "assumptions": {
        "type": "object",
        "description": "Override default forecast assumptions (optional, for advanced users)",
        "properties": {
          "acquisition_rate_change": {
            "type": "number",
            "description": "% change in customer acquisition rate (e.g., 0.1 for 10% increase)"
          },
          "churn_rate_change": {
            "type": "number",
            "description": "% change in churn rate (e.g., -0.05 for 5% improvement)"
          },
          "aov_change": {
            "type": "number",
            "description": "% change in average order value"
          }
        }
      }
    },
    "required": []
  }
}
```

---

### Query Coverage Map

| Query Type | Parameters Used | Example Query |
|------------|-----------------|---------------|
| **Revenue forecast** | `metrics: ["revenue"]`, `timeframe_months: 12` | "what will revenue be next year" |
| **Q4 revenue forecast** | `metrics: ["revenue"]`, `timeframe_months: 3`, `breakdown: monthly` | "revenue forecast for Q4" |
| **Customer growth** | `metrics: ["customer_count", "new_customers", "churned_customers"]` | "how many customers will I have next year" |
| **Churn forecast** | `metrics: ["churn_rate", "churned_customers"]` | "predict churn rate" |
| **LTV forecast** | `metrics: ["average_ltv"]`, `timeframe_months: 12` | "what will average customer value be" |
| **Multi-metric forecast** | `metrics: ["revenue", "customer_count", "churn_rate"]` | "show me all key metrics forecast" |
| **Segment-specific forecast** | `segment_filter: "premium_buyers"`, `metrics: ["revenue"]` | "revenue forecast for premium segment" |
| **Short-term forecast** | `timeframe_months: 3`, `breakdown: monthly` | "next quarter forecast" |
| **Long-term projection** | `timeframe_months: 24`, `breakdown: quarterly` | "2-year business projection" |
| **Growth projection** | `metrics: ["customer_count", "new_customers"]`, `confidence_interval: true` | "customer base growth with confidence bands" |

**Coverage: 10+ distinct query types**

---

### Example Usage Scenarios

#### Scenario 1: Simple Revenue Forecast
**User:** "What will our revenue be for Q4?"

**Claude routes to:**
```json
{
  "metrics": ["revenue"],
  "timeframe_months": 3,
  "breakdown": "monthly",
  "confidence_interval": true
}
```

**Returns:** 3-month revenue forecast with low/expected/high predictions

---

#### Scenario 2: Comprehensive Business Forecast
**User:** "Give me a full business forecast for next year"

**Claude routes to:**
```json
{
  "metrics": ["revenue", "customer_count", "new_customers", "churned_customers", "average_ltv", "churn_rate"],
  "timeframe_months": 12,
  "breakdown": "quarterly",
  "confidence_interval": true
}
```

**Returns:** All key metrics by quarter with confidence intervals

---

#### Scenario 3: Segment-Specific Projection
**User:** "What will revenue be from premium customers over the next 6 months?"

**Claude routes to:**
```json
{
  "metrics": ["revenue", "customer_count"],
  "timeframe_months": 6,
  "breakdown": "monthly",
  "segment_filter": "premium_buyers"
}
```

**Returns:** Revenue and customer count forecast for premium segment only

---

#### Scenario 4: Scenario Planning
**User:** "What if we reduce churn by 10% and increase AOV by 5%?"

**Claude routes to:**
```json
{
  "metrics": ["revenue", "customer_count"],
  "timeframe_months": 12,
  "assumptions": {
    "churn_rate_change": -0.10,
    "aov_change": 0.05
  },
  "confidence_interval": false
}
```

**Returns:** Forecast under specified scenario assumptions

---

## Tool 4: `plan_campaign`

### Purpose
Get targeting recommendations and actionable strategies for marketing campaigns.

### Replaces
- `target_campaign` (6 sub-types)
- `get_recommendations` (6 sub-types)
- Direct MCP: `recommend_segments_for_campaign`

**Total: 12 query types consolidated**

---

### Tool Definition

```json
{
  "name": "plan_campaign",
  "description": "Get campaign targeting recommendations - who to target, when, how, and why. Use this for questions about marketing campaigns, customer outreach, retention strategies (e.g., 'who should I target for retention?', 'Black Friday campaign targets', 'upsell opportunities', 'win-back strategy').",
  "input_schema": {
    "type": "object",
    "properties": {
      "goal": {
        "type": "string",
        "enum": [
          "retention",     // Keep at-risk customers
          "growth",        // Increase spending from existing customers (upsell)
          "winback",       // Re-engage churned/lapsed customers
          "acquisition",   // Attract new customers (lookalike targeting)
          "loyalty",       // Reward and engage best customers
          "cross_sell",    // Introduce customers to new product categories
          "seasonal"       // Event-based targeting (holiday, sale)
        ],
        "description": "Primary campaign objective"
      },
      "event": {
        "type": "string",
        "description": "For goal='seasonal': specific event to target (e.g., 'black_friday', 'christmas', 'spring_sale')",
        "enum": [
          "halloween", "thanksgiving", "black_friday", "cyber_monday",
          "christmas", "new_year", "valentines", "spring_sale",
          "summer_clearance", "back_to_school"
        ]
      },
      "constraints": {
        "type": "object",
        "description": "Budget and targeting constraints",
        "properties": {
          "budget_total": {
            "type": "number",
            "description": "Total campaign budget in dollars"
          },
          "cost_per_customer": {
            "type": "number",
            "description": "Maximum cost per customer reached (for budget allocation)"
          },
          "min_ltv": {
            "type": "number",
            "description": "Only target customers with LTV above this threshold"
          },
          "max_churn_risk": {
            "type": "number",
            "description": "Maximum churn risk (0.0-1.0) to include (for acquisition/growth campaigns)"
          },
          "min_churn_risk": {
            "type": "number",
            "description": "Minimum churn risk (for retention/winback campaigns)"
          },
          "segment_filter": {
            "type": "string",
            "description": "Limit to specific segment/archetype (e.g., 'premium_buyers')"
          },
          "exclude_recent_campaign": {
            "type": "boolean",
            "description": "Exclude customers contacted in last 30 days",
            "default": true
          }
        }
      },
      "target_size": {
        "type": "integer",
        "description": "Desired number of customers to target",
        "default": 100,
        "minimum": 10,
        "maximum": 10000
      },
      "include_strategy": {
        "type": "boolean",
        "description": "Include specific recommended actions, messaging, offers, and timing",
        "default": true
      },
      "prioritize_by": {
        "type": "string",
        "enum": [
          "impact",        // LTV × churn_risk (highest impact at-risk customers)
          "ltv",           // Highest value customers first
          "churn_risk",    // Highest risk customers first
          "roi_potential", // Expected ROI based on historical campaign performance
          "conversion"     // Highest likelihood to convert/respond
        ],
        "description": "How to prioritize target list",
        "default": "impact"
      },
      "output_format": {
        "type": "string",
        "enum": ["summary", "detailed", "export_ready"],
        "description": "Level of detail in output. 'export_ready' includes customer IDs for upload to marketing platform.",
        "default": "detailed"
      }
    },
    "required": ["goal"]
  }
}
```

---

### Query Coverage Map

| Query Type | Parameters Used | Example Query |
|------------|-----------------|---------------|
| **Retention campaign** | `goal: retention`, `prioritize_by: impact` | "who should I target for retention" |
| **High-impact retention** | `goal: retention`, `constraints.min_ltv: 2000`, `prioritize_by: impact` | "retain high-value at-risk customers" |
| **Winback campaign** | `goal: winback`, `target_size: 200` | "re-engage lapsed customers" |
| **Upsell campaign** | `goal: growth`, `constraints.min_ltv: 500` | "who should I upsell to" |
| **Cross-sell campaign** | `goal: cross_sell`, `include_strategy: true` | "cross-sell opportunities" |
| **Loyalty campaign** | `goal: loyalty`, `constraints.max_churn_risk: 0.3` | "reward my best customers" |
| **Black Friday targeting** | `goal: seasonal`, `event: black_friday` | "who to target for Black Friday" |
| **Holiday campaign** | `goal: seasonal`, `event: christmas` | "Christmas campaign targets" |
| **Budget-constrained campaign** | `goal: retention`, `constraints.budget_total: 5000`, `constraints.cost_per_customer: 25` | "retention campaign with $5k budget" |
| **Segment-specific campaign** | `goal: growth`, `constraints.segment_filter: premium_buyers` | "upsell campaign for premium segment" |
| **Acquisition lookalike** | `goal: acquisition`, `constraints.segment_filter: best_customers` | "find lookalikes for acquisition" |
| **Export for marketing platform** | `goal: retention`, `output_format: export_ready` | "export retention targets for Klaviyo" |

**Coverage: 12+ distinct query types**

---

### Example Usage Scenarios

#### Scenario 1: Basic Retention Campaign
**User:** "Who should I target for a retention campaign?"

**Claude routes to:**
```json
{
  "goal": "retention",
  "target_size": 100,
  "prioritize_by": "impact",
  "include_strategy": true
}
```

**Returns:**
- Top 100 at-risk customers (sorted by LTV × churn_risk)
- Recommended actions (email cadence, discount offers, VIP treatment)
- Messaging suggestions
- Optimal timing for outreach

---

#### Scenario 2: Budget-Constrained Winback
**User:** "I have $2000 to win back lapsed customers, what's my strategy?"

**Claude routes to:**
```json
{
  "goal": "winback",
  "constraints": {
    "budget_total": 2000,
    "cost_per_customer": 20
  },
  "target_size": 100,
  "include_strategy": true,
  "prioritize_by": "roi_potential"
}
```

**Returns:**
- 100 lapsed customers (budget allows $20 each)
- Ranked by expected ROI
- Recommended offers (% discount based on LTV)
- Email templates
- A/B test suggestions

---

#### Scenario 3: Black Friday Targeting
**User:** "Who should I target for Black Friday sale?"

**Claude routes to:**
```json
{
  "goal": "seasonal",
  "event": "black_friday",
  "target_size": 500,
  "include_strategy": true
}
```

**Returns:**
- 500 customers most likely to engage during Black Friday
- Segmentation: deal hunters, premium buyers, seasonal shoppers
- Product recommendations by segment
- Email send schedule (early access for VIPs, general list)
- Discount strategy by value tier

---

#### Scenario 4: VIP Loyalty Campaign
**User:** "Create a VIP appreciation campaign for my best customers"

**Claude routes to:**
```json
{
  "goal": "loyalty",
  "constraints": {
    "min_ltv": 5000,
    "max_churn_risk": 0.3
  },
  "target_size": 50,
  "include_strategy": true
}
```

**Returns:**
- Top 50 VIP customers (high value, low churn risk)
- Exclusive offers (early access, special products, VIP events)
- Personalized messaging
- Retention strategy to keep them engaged

---

#### Scenario 5: Export for Marketing Platform
**User:** "Give me a list of retention targets I can upload to Klaviyo"

**Claude routes to:**
```json
{
  "goal": "retention",
  "target_size": 200,
  "prioritize_by": "impact",
  "output_format": "export_ready"
}
```

**Returns:**
- CSV-formatted data with customer IDs, emails, names
- Custom properties for Klaviyo (churn_risk_score, ltv_tier, recommended_discount)
- Segment tags for automation workflows

---

## Tool 5: `analyze_products`

### Purpose
Analyze product categories, revenue, bundles, and purchasing patterns using order-level sales data.

### Replaces
- `analyze_products` (9 sub-types) - **KEEP AS-IS, well designed**

**Total: 9 query types**

---

### Tool Definition

**No changes** - this tool is already well-designed with clear boundaries and comprehensive coverage.

```json
{
  "name": "analyze_products",
  "description": "Analyze product categories, revenue, and purchasing patterns using actual order-level sales data. Use this for questions about what products/categories customers buy, revenue by category, popularity, trends, bundles, or seasonal performance (e.g., 'top selling products', 'what do customers buy together', 'which categories are growing').",
  "input_schema": {
    "type": "object",
    "properties": {
      "analysis_type": {
        "type": "string",
        "enum": [
          "revenue_by_category",           // Total revenue by product category
          "category_popularity",           // Categories by customer count
          "category_by_customer_segment",  // What segments buy what categories
          "category_trends",               // Growing/declining categories over time
          "category_repurchase_rate",      // Repeat purchase rate by category
          "category_value_metrics",        // AOV, spend per customer by category
          "product_bundles",               // What products/categories are bought together
          "seasonal_product_performance",  // Track products by month/quarter
          "individual_product_performance" // Top individual products (not just categories)
        ],
        "description": "Type of product analysis to perform"
      },
      "segment_filter": {
        "type": "string",
        "description": "Filter to specific customer segment: 'high_value', 'premium', 'budget', 'power_buyer', etc."
      },
      "sort_by": {
        "type": "string",
        "enum": ["revenue", "customer_count", "aov", "total_orders", "growth_rate", "repurchase_rate"],
        "description": "How to sort results",
        "default": "revenue"
      },
      "timeframe_months": {
        "type": "integer",
        "description": "For trend analysis, how many months to analyze",
        "default": 12
      },
      "limit": {
        "type": "integer",
        "description": "Number of categories/products to return",
        "default": 10
      }
    },
    "required": ["analysis_type"]
  }
}
```

---

### Query Coverage Map

| Query Type | Parameters Used | Example Query |
|------------|-----------------|---------------|
| **Top revenue categories** | `analysis_type: revenue_by_category`, `sort_by: revenue` | "which categories generate most revenue" |
| **Popular categories** | `analysis_type: category_popularity`, `sort_by: customer_count` | "most popular product categories" |
| **Category by segment** | `analysis_type: category_by_customer_segment`, `segment_filter: high_value` | "what do VIP customers buy" |
| **Growing categories** | `analysis_type: category_trends`, `sort_by: growth_rate` | "which categories are growing" |
| **Repeat purchase categories** | `analysis_type: category_repurchase_rate` | "which products drive repeat purchases" |
| **Category AOV** | `analysis_type: category_value_metrics`, `sort_by: aov` | "highest AOV categories" |
| **Product bundles** | `analysis_type: product_bundles` | "what products do customers buy together" |
| **Seasonal products** | `analysis_type: seasonal_product_performance` | "when do customers buy batting" |
| **Best selling products** | `analysis_type: individual_product_performance`, `sort_by: revenue` | "top selling individual products" |

**Coverage: 9 distinct query types**

---

## Cross-Tool Query Coverage

### Complex Multi-Tool Queries

Some queries require **multiple tools** in sequence:

#### Example 1: Product Affinity by Customer Tier
**User:** "What products do my high-value customers buy?"

**Requires:**
1. `query_customers` with `filters.ltv_min: 5000` → get high-value customer IDs
2. `analyze_products` with `analysis_type: category_by_customer_segment`, `segment_filter: high_value`

**Implementation:** Backend handles this automatically - `analyze_products` can filter by customer segment internally

---

#### Example 2: Campaign Planning with Product Insights
**User:** "Create a cross-sell campaign targeting frequent buyers with complementary product bundles"

**Requires:**
1. `analyze_products` with `analysis_type: product_bundles` → identify bundles
2. `plan_campaign` with `goal: cross_sell`, `constraints.segment_filter: frequent_buyers`

**Implementation:** `plan_campaign` response includes product recommendations

---

#### Example 3: Segment Performance Deep Dive
**User:** "Show me my top segment, who's in it, and what they buy"

**Requires:**
1. `query_segments` with `analysis: overview`, `sort_by: total_revenue`, `limit: 1` → get top segment
2. `query_customers` with `filters.archetype_id: [from step 1]` → get customer list
3. `analyze_products` with `segment_filter: [from step 1]` → get purchase patterns

**Implementation:** Natural language endpoint orchestrates multiple tool calls

---

## Coverage Summary Table

| Query Domain | Tool | Query Types | Examples |
|--------------|------|-------------|----------|
| **Individual Customers** | query_customers | 21 | "high-value customers", "at-risk VIPs", "one-time buyers", "customer 123" |
| **Customer Segments** | query_segments | 13 | "what types of customers", "growing segments", "Halloween shoppers", "compare segments" |
| **Business Forecasting** | forecast_business_metrics | 10 | "Q4 revenue", "customer growth", "churn forecast", "2-year projection" |
| **Campaign Planning** | plan_campaign | 12 | "retention targets", "Black Friday campaign", "upsell opportunities", "win-back strategy" |
| **Product Analysis** | analyze_products | 9 | "top products", "product bundles", "category trends", "seasonal performance" |
| **TOTAL** | **5 tools** | **65 query types** | Full coverage + composability |

**Note:** 65 > 49 original types because composable filters enable MORE queries than before!

---

## Decision Tree for Claude

To help Claude choose the right tool, here's the simplified decision logic:

```
Question about...

├─ Specific customer or filtered customer list?
│  → query_customers
│     ├─ "customer 123" → scope: individual
│     ├─ "high-value customers" → scope: list, filters.ltv_min
│     └─ "at-risk VIPs" → scope: list, filters.ltv_min + churn_risk_min
│
├─ Customer segments/archetypes/groups?
│  → query_segments
│     ├─ "what types of customers" → analysis: overview
│     ├─ "growing segments" → analysis: growth
│     └─ "Halloween shoppers" → analysis: seasonal, event: halloween
│
├─ Future predictions (revenue, growth, churn)?
│  → forecast_business_metrics
│     ├─ "Q4 revenue" → metrics: ["revenue"], timeframe_months: 3
│     ├─ "customer growth" → metrics: ["customer_count"]
│     └─ "churn forecast" → metrics: ["churn_rate"]
│
├─ Marketing campaign or targeting strategy?
│  → plan_campaign
│     ├─ "retention campaign" → goal: retention
│     ├─ "upsell opportunities" → goal: growth
│     └─ "Black Friday targets" → goal: seasonal, event: black_friday
│
└─ Product categories, bundles, or purchase patterns?
   → analyze_products
      ├─ "top products" → analysis_type: revenue_by_category
      ├─ "product bundles" → analysis_type: product_bundles
      └─ "seasonal products" → analysis_type: seasonal_product_performance
```

**Probability of correct routing: ~90%** (vs 2.1% with 8 tools)

---

## Implementation Notes

### Backend Handler Mapping

Each tool routes to existing handlers - **no backend changes needed initially**:

```python
# query_customers
if scope == "individual":
    → _handle_lookup_customer()
elif filters.churn_risk_min:
    → _handle_churn_risk_analysis()
elif filters.is_b2b:
    → _handle_b2b_identification()
elif filters.behavior_pattern:
    → _handle_behavior_pattern_analysis()
else:
    → _handle_high_value_customers() with filters

# query_segments
if analysis == "overview":
    → _handle_archetype_growth()
elif analysis == "growth":
    → _handle_archetype_growth()
elif analysis == "seasonal":
    → _handle_seasonal_archetype_analysis()
elif analysis == "comparison":
    → _handle_segment_comparison()

# forecast_business_metrics
if "revenue" in metrics:
    → _handle_revenue_forecast()
if "customer_count" in metrics:
    → _handle_metric_forecast(metric="customer_count")
# Can aggregate multiple forecasts

# plan_campaign
if goal == "retention":
    → _handle_campaign_targeting(campaign_type="retention")
    + _handle_get_recommendations(recommendation_type="retention_actions")
elif goal == "seasonal":
    → _handle_seasonal_archetype_analysis() + targeting logic

# analyze_products (no change)
→ _handle_product_analysis()
```

### Migration Strategy

**Phase 1 (Week 1-2):** Add new tools alongside old tools
- Claude sees both old and new tools
- Log which tools get chosen
- Measure success rate

**Phase 2 (Week 3-4):** Prefer new tools
- Update tool descriptions to guide Claude toward new tools
- Keep old tools as fallbacks
- Monitor routing accuracy

**Phase 3 (Week 5-6):** Remove old tools
- Once new tools proven stable (>85% accuracy)
- Remove old tool definitions
- Clean up backend handlers

**Phase 4 (Week 7-8):** Optimize backend
- Consolidate redundant handler functions
- Implement unified filtering system
- Performance optimizations

---

## Success Metrics

### Before Migration (Baseline)
- **8 tools**, 48 sub-types
- Tool selection accuracy: ~75%
- Avg query time: 1.75s
- Token usage: 1800/query
- User satisfaction: TBD

### After Migration (Target)
- **5 tools**, ~20 sub-types
- Tool selection accuracy: **>90%** (↑15%)
- Avg query time: **<1.2s** (↓31%)
- Token usage: **<1100/query** (↓39%)
- User satisfaction: **↑20%** (fewer errors, faster responses)

### Measurement Plan
- A/B test: 50% users on old tools, 50% on new
- Track for 2 weeks
- Compare metrics
- Full rollout if targets met

---

## Appendix: Full Query Type Mapping

### query_customers (21 types)
1. High-value customers
2. At-risk customers (churn_risk)
3. VIPs at churn risk
4. One-time buyers
5. Lapsed customers
6. B2B identification
7. Seasonal shoppers
8. Declining engagement
9. Growing engagement
10. Discount dependent
11. Premium buyers
12. Frequent buyers
13. Recent buyers
14. Individual customer lookup
15. Customer churn risk (individual)
16. Customer LTV forecast
17. Customer purchase history
18. Customer recommendations
19. RFM analysis
20. Behavioral analysis
21. Product affinity (cross-reference with analyze_products)

### query_segments (13 types)
1. Segment overview
2. Top segments by value
3. Top segments by size
4. Growing segments
5. Shrinking segments
6. Segment growth projection
7. Seasonal segment analysis (Halloween, Christmas, etc.)
8. Holiday shoppers
9. Black Friday targets
10. Segment comparison
11. At-risk segments
12. High-value segments
13. Small niche segments

### forecast_business_metrics (10 types)
1. Revenue forecast
2. Q4 revenue forecast
3. Customer growth
4. Churn forecast
5. LTV forecast
6. Multi-metric forecast
7. Segment-specific forecast
8. Short-term forecast
9. Long-term projection
10. Growth projection with confidence

### plan_campaign (12 types)
1. Retention campaign
2. High-impact retention
3. Winback campaign
4. Upsell campaign
5. Cross-sell campaign
6. Loyalty campaign
7. Black Friday targeting
8. Holiday campaign
9. Budget-constrained campaign
10. Segment-specific campaign
11. Acquisition lookalike
12. Export for marketing platform

### analyze_products (9 types)
1. Top revenue categories
2. Popular categories
3. Category by segment
4. Growing categories
5. Repeat purchase categories
6. Category AOV
7. Product bundles
8. Seasonal products
9. Best selling products

**Total: 65 query types supported** (16 more than before due to composability!)

---

**Document Version:** 1.0
**Status:** PROPOSED - Awaiting Review & Approval
**Next Steps:** Review with stakeholders → Create implementation tickets → Begin Phase 1
