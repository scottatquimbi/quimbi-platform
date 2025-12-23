# API Documentation

**Customer Intelligence Platform REST API**

Base URL: `https://ecommerce-backend-staging-a14c.up.railway.app`

---

## Table of Contents

1. [Authentication](#authentication)
2. [Core Endpoints](#core-endpoints)
3. [Analytics Endpoints](#analytics-endpoints)
4. [MCP Tool Endpoints](#mcp-tool-endpoints)
5. [Response Formats](#response-formats)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Examples](#examples)

---

## Authentication

Currently, the API is **open** with no authentication required. Future versions may add API key authentication.

---

## Core Endpoints

### GET /health

**Description:** System health check and data availability status

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-16T20:20:07.654425",
  "version": "1.0.0",
  "components": {
    "api": "healthy",
    "mcp_server": "healthy",
    "database": "healthy"
  },
  "data_status": {
    "customers_loaded": 27415,
    "archetypes_available": 868,
    "data_source": "postgresql"
  }
}
```

**Status Codes:**
- `200 OK` - System is healthy
- `503 Service Unavailable` - System is down or data not loaded

---

### GET /api/mcp/customer/random

**Description:** Get a random customer profile from the database

**Response:**
```json
{
  "customer_id": "7827249201407",
  "archetype": {
    "archetype_id": "arch_763094",
    "dominant_segments": {
      "purchase_value": "mid_tier",
      "return_behavior": "careful_buyer",
      "shopping_cadence": "weekend_crafter",
      "category_affinity": "category_loyal",
      "price_sensitivity": "deal_hunter",
      "shopping_maturity": "established",
      "purchase_frequency": "regular",
      "repurchase_behavior": "variety_seeker"
    },
    "behavioral_traits": [
      "category_affinity:category_loyal",
      "price_sensitivity:deal_hunter",
      "purchase_frequency:regular"
    ],
    "member_count": 67,
    "population_percentage": 0.24
  },
  "business_metrics": {
    "lifetime_value": 66.57,
    "total_orders": 2,
    "avg_order_value": 33.28,
    "days_since_last_purchase": 139,
    "customer_tenure_days": 245
  }
}
```

**Status Codes:**
- `200 OK` - Customer returned
- `503 Service Unavailable` - No customers loaded

---

### GET /api/mcp/customer/{customer_id}

**Description:** Get specific customer's behavioral profile

**Parameters:**
- `customer_id` (path) - 13-digit customer ID

**Response:** Same as random customer endpoint

**Status Codes:**
- `200 OK` - Customer found
- `404 Not Found` - Customer ID not found
- `500 Internal Server Error` - Query failed

---

### GET /api/mcp/customer/{customer_id}/churn-risk

**Description:** Predict churn risk for specific customer

**Parameters:**
- `customer_id` (path) - 13-digit customer ID

**Response:**
```json
{
  "customer_id": "7827249201407",
  "risk_level": "low",
  "churn_risk_score": 0.15,
  "factors": {
    "recency_days": 139,
    "order_frequency": "regular",
    "value_tier": "mid_tier",
    "engagement_trend": "stable"
  },
  "recommendation": "Monitor for changes in purchase frequency. Consider seasonal engagement campaign."
}
```

**Risk Levels:**
- `"high"` - churn_risk_score > 0.7
- `"medium"` - 0.3 < churn_risk_score ≤ 0.7
- `"low"` - churn_risk_score ≤ 0.3

**Status Codes:**
- `200 OK` - Risk calculated
- `404 Not Found` - Customer not found
- `500 Internal Server Error` - Prediction failed

---

## Analytics Endpoints

### GET /api/mcp/churn/aggregate

**Description:** Aggregate churn risk analysis across customer base

**Response:**
```json
{
  "total_customers": 27415,
  "sample_size": 1000,
  "churn_risk_distribution": {
    "high_risk": {
      "count": 0,
      "percentage": 0.0,
      "estimated_total": 0
    },
    "medium_risk": {
      "count": 0,
      "percentage": 0.0,
      "estimated_total": 0
    },
    "low_risk": {
      "count": 1000,
      "percentage": 100.0,
      "estimated_total": 27415
    }
  },
  "estimated_churn_30_days": 0,
  "estimated_churn_90_days": 0,
  "note": "Analysis based on random sample of 1000 customers from 27415 total"
}
```

**Status Codes:**
- `200 OK` - Analysis complete
- `503 Service Unavailable` - No customers loaded
- `500 Internal Server Error` - Analysis failed

---

### GET /api/mcp/growth/projection

**Description:** Project customer base growth over time

**Parameters:**
- `months` (query, optional) - Number of months to project (default: 12)
  - Valid values: 6, 12, 18, 24

**Response:**
```json
{
  "current_customers": 27415,
  "projected_customers": 33259,
  "timeframe_months": 12,
  "total_acquired": 5844,
  "total_churned": 0,
  "net_change": 5844,
  "growth_rate_pct": 21.32,
  "monthly_projections": [
    {
      "month": 1,
      "customers": 27903,
      "acquired": 488,
      "churned": 0,
      "net_change": 488
    }
  ],
  "assumptions": {
    "monthly_acquisition_rate": 488,
    "monthly_churn_rate_pct": 0.0,
    "avg_customer_tenure_days": 717,
    "data_span_years": 2.1
  },
  "note": "Projection based on historical acquisition patterns from 1000 customer sample"
}
```

**Status Codes:**
- `200 OK` - Projection calculated
- `400 Bad Request` - Invalid months parameter
- `503 Service Unavailable` - No customers loaded
- `500 Internal Server Error` - Projection failed

---

### GET /api/mcp/archetypes/top

**Description:** Get top archetypes ranked by specified metric

**Parameters:**
- `metric` (query, optional) - Ranking metric (default: "total_ltv")
  - `"total_ltv"` - Total lifetime value across all members
  - `"avg_ltv"` - Average LTV per member
  - `"member_count"` - Number of members
- `limit` (query, optional) - Number of top archetypes to return (default: 10)

**Response:**
```json
{
  "metric": "total_ltv",
  "total_archetypes": 868,
  "top_archetypes": [
    {
      "archetype_id": "arch_650665",
      "dominant_segments": {
        "purchase_value": "mid_tier",
        "return_behavior": "careful_buyer",
        "shopping_cadence": "weekday",
        "category_affinity": "multi_category",
        "price_sensitivity": "deal_hunter",
        "shopping_maturity": "established",
        "purchase_frequency": "regular",
        "repurchase_behavior": "variety_seeker"
      },
      "member_count": 814,
      "total_lifetime_value": 1316563.14,
      "avg_lifetime_value": 1617.69,
      "population_percentage": 2.97
    }
  ],
  "summary": {
    "top_archetype_total_ltv": 10450321.50,
    "top_archetype_member_count": 5123,
    "top_archetype_population_pct": 18.69
  }
}
```

**Status Codes:**
- `200 OK` - Archetypes returned
- `400 Bad Request` - Invalid metric parameter
- `503 Service Unavailable` - No archetypes loaded
- `500 Internal Server Error` - Query failed

---

### GET /api/mcp/archetypes/growth-projection

**Description:** Project growth/churn for top archetypes over time

**Parameters:**
- `months` (query, optional) - Number of months to project (default: 12)
- `top_n` (query, optional) - Number of top archetypes to analyze (default: 10)

**Response:**
```json
{
  "timeframe_months": 12,
  "archetypes_analyzed": 10,
  "archetype_projections": [
    {
      "archetype_id": "arch_650665",
      "dominant_segments": {
        "purchase_value": "mid_tier",
        "return_behavior": "careful_buyer",
        "shopping_cadence": "weekday"
      },
      "current_members": 814,
      "projected_members": 982,
      "total_ltv": 1316563.14,
      "net_change": 168,
      "growth_rate_pct": 20.64,
      "total_acquired": 168,
      "total_churned": 0,
      "monthly_churn_rate_pct": 0.0
    }
  ],
  "global_assumptions": {
    "total_monthly_acquisition": 488,
    "data_span_years": 2.1
  }
}
```

**Status Codes:**
- `200 OK` - Projections calculated
- `503 Service Unavailable` - No data loaded
- `500 Internal Server Error` - Projection failed

---

### GET /api/mcp/customer/{customer_id}/next-purchase

**Description:** Predict when a customer will make their next purchase based on historical patterns

**Parameters:**
- `customer_id` (path, required) - Customer ID

**Response:**
```json
{
  "customer_id": "7827249201407",
  "prediction_available": true,
  "next_purchase_prediction": {
    "predicted_date": "2025-12-15",
    "days_from_now": 45,
    "confidence": 0.85
  },
  "purchase_pattern": {
    "avg_days_between_purchases": 42.3,
    "days_since_last_purchase": 15,
    "total_orders": 8,
    "shopping_cadence": "regular",
    "purchase_frequency": "power_buyer"
  },
  "recommendation": "Reach out in 40 days with personalized offer"
}
```

**Status Codes:**
- `200 OK` - Prediction calculated
- `404 Not Found` - Customer not found
- `500 Internal Server Error` - Prediction failed

---

### GET /api/mcp/customer/{customer_id}/ltv-forecast

**Description:** Forecast customer lifetime value over specified period

**Parameters:**
- `customer_id` (path, required) - Customer ID
- `months` (query, optional) - Forecast timeframe in months (default: 12)

**Response:**
```json
{
  "customer_id": "7827249201407",
  "forecast_available": true,
  "timeframe_months": 12,
  "current_ltv": 523.71,
  "projected_ltv": 698.45,
  "ltv_increase": 174.74,
  "growth_rate_pct": 33.4,
  "monthly_projections": [
    {
      "month": 1,
      "cumulative_ltv": 537.82,
      "month_value": 14.11,
      "retention_probability": 0.967,
      "expected_orders": 0.23
    }
  ],
  "assumptions": {
    "monthly_order_rate": 0.25,
    "avg_order_value": 61.84,
    "churn_risk_score": 0.15,
    "monthly_retention_rate": 0.987
  },
  "comparison": {
    "archetype_avg_ltv": 645.23,
    "performance_vs_archetype": "below"
  }
}
```

**Status Codes:**
- `200 OK` - Forecast calculated
- `404 Not Found` - Customer not found
- `500 Internal Server Error` - Forecast failed

---

### GET /api/mcp/revenue/forecast

**Description:** Forecast total revenue over specified period based on customer LTV projections

**Parameters:**
- `months` (query, optional) - Forecast timeframe in months (default: 12)

**Response:**
```json
{
  "timeframe_months": 12,
  "current_total_ltv": 38547231.45,
  "projected_total_ltv": 46892441.67,
  "revenue_increase": 8345210.22,
  "growth_rate_pct": 21.65,
  "monthly_breakdown": [
    {
      "month": 1,
      "monthly_revenue": 642341.23,
      "cumulative_revenue": 39189572.68
    }
  ],
  "assumptions": {
    "sample_size": 1000,
    "total_customers": 27415,
    "extrapolation_factor": 27.42
  },
  "note": "Forecast based on 1000 customer sample, extrapolated to full population"
}
```

**Status Codes:**
- `200 OK` - Forecast calculated
- `503 Service Unavailable` - No customers loaded
- `500 Internal Server Error` - Forecast failed

---

### POST /api/mcp/campaigns/recommend

**Description:** Recommend customers for targeted marketing campaigns

**Parameters:**
- `campaign_type` (query, optional) - Campaign type: "retention", "growth", or "winback" (default: "retention")
- `target_size` (query, optional) - Number of customers to recommend (default: 100)
- `min_ltv` (query, optional) - Minimum LTV threshold (default: 0)

**Campaign Types:**
- **retention** - High value + high churn risk customers (prevent loss)
- **growth** - High value + low churn customers (upsell opportunities)
- **winback** - Inactive customers with historical value (re-engagement)

**Response:**
```json
{
  "campaign_type": "retention",
  "target_size_requested": 100,
  "recommendations_count": 100,
  "recommended_customers": [
    {
      "customer_id": "7827249201407",
      "score": 892.45,
      "ltv": 1234.56,
      "churn_risk": 0.72,
      "risk_level": "high",
      "archetype": "arch_763094",
      "dominant_segments": {...}
    }
  ],
  "aggregate_metrics": {
    "total_ltv": 123456.78,
    "avg_ltv": 1234.57,
    "avg_churn_risk": 0.68,
    "min_ltv_filter": 0
  },
  "archetype_distribution": {
    "arch_763094": 23,
    "arch_650665": 18
  },
  "campaign_recommendations": "Focus on preventing churn from high-value customers"
}
```

**Status Codes:**
- `200 OK` - Recommendations calculated
- `400 Bad Request` - Invalid campaign_type
- `503 Service Unavailable` - No customers loaded
- `500 Internal Server Error` - Recommendation failed

---

### POST /admin/sync-status

**Description:** Check status of sales data and diagnostic information (admin only)

**Authentication:** Requires `ADMIN_KEY` environment variable

**Query Parameters:**
- `admin_key` (required) - Admin authentication key

**Response:**
```json
{
  "sync_info": {
    "database_url": "postgresql://...",
    "table_exists": true,
    "table_name": "combined_sales"
  },
  "row_count": 1221736,
  "latest_record": {
    "order_date": "2025-10-22T00:00:00",
    "order_id": 5234567890
  },
  "date_range": {
    "earliest": "2021-01-26T00:00:00",
    "latest": "2025-10-22T00:00:00"
  }
}
```

**Status Codes:**
- `200 OK` - Status retrieved
- `403 Forbidden` - Invalid admin key
- `500 Internal Server Error` - Query failed

---

### POST /admin/sync-sales

**Description:** Manually trigger sales data sync (admin only)

**Authentication:** Requires `ADMIN_KEY` environment variable

**Query Parameters:**
- `mode` (optional) - Sync mode: "dry-run", "incremental", or "full" (default: "dry-run")
- `limit` (optional) - Limit number of rows (for testing)
- `admin_key` (required) - Admin authentication key

**Response:**
```json
{
  "status": "success",
  "mode": "dry-run",
  "stdout": "✅ Connected to Azure SQL\n✅ Fetched 1000 rows\n[DRY RUN] Would load to Postgres"
}
```

**Status Codes:**
- `200 OK` - Sync completed
- `403 Forbidden` - Invalid admin key
- `500 Internal Server Error` - Sync failed

**Example:**
```bash
curl -X POST "https://your-app.railway.app/admin/sync-sales?mode=dry-run&limit=100&admin_key=your-secret-key"
```

---

### POST /api/mcp/query/natural-language

**Description:** AI-powered natural language query router using Claude 3.5 Haiku function calling

**How It Works:**
This endpoint uses Claude AI to interpret natural language business questions and intelligently route them to the appropriate analysis endpoint. No keyword matching - Claude understands intent, context, and automatically extracts parameters.

**Parameters:**
- `query` (query param, required) - Natural language question in any phrasing

**Architecture:**
1. Query sent to Claude 3.5 Haiku with 4 flexible tool definitions
2. Claude analyzes intent and selects appropriate tool + parameters
3. Claude extracts parameters (analysis type, timeframes, metrics, etc.)
4. System routes to corresponding handler based on tool + analysis_type
5. Results returned with original query context

**Supported Tools (Redesigned for Flexibility):**

1. **Customer Analysis** (`analyze_customers` tool)
   - **Purpose:** Analyze and identify specific customer groups
   - **Analysis Types:**
     - `churn_risk` - Customers at risk of leaving
     - `b2b_identification` - Identify business customers (high order volume, large orders)
     - `high_value` - Top customers by LTV
     - `behavioral` - Custom behavioral patterns
     - `product_affinity` - Category/product preferences
     - `rfm_score` - Recency, Frequency, Monetary scoring
   - **Parameters:**
     - `analysis_type` - Type of customer analysis
     - `sort_by` - ltv, churn_risk, impact, frequency, recency, orders
     - `limit` - Number of customers to return (default: 100)
     - `filter_by` - Custom filter string

2. **Segment Analysis** (`analyze_segments` tool)
   - **Purpose:** Analyze customer segments/archetypes - who they are, how they behave
   - **Analysis Types:**
     - `segment_overview` - Overview of top customer segments
     - `segment_growth` - How segments will grow/shrink over time
     - `seasonal_segments` - Segments engaged during holidays/events
     - `segment_comparison` - Compare multiple segments
   - **Parameters:**
     - `analysis_type` - Type of segment analysis
     - `event_type` - For seasonal: halloween, christmas, black_friday, etc.
     - `timeframe_months` - Projection timeframe (default: 12)
     - `top_n` - Number of segments (default: 10)

3. **Metric Forecasting** (`forecast_metrics` tool)
   - **Purpose:** Forecast future business metrics
   - **Metrics:**
     - `revenue` - Revenue projection
     - `customer_count` - Customer growth projection
     - `average_ltv` - Average customer value projection
     - `churn_rate` - Churn rate trends
   - **Parameters:**
     - `metric` - Which metric to forecast
     - `timeframe_months` - Forecast period (default: 12)

4. **Campaign Targeting** (`target_campaign` tool)
   - **Purpose:** Recommend customers for marketing campaigns
   - **Campaign Types:**
     - `retention` - Keep at-risk customers
     - `growth` - Expand high-value relationships
     - `winback` - Re-engage churned customers
     - `seasonal` - Holiday/event campaigns
     - `loyalty` - Reward programs
     - `acquisition` - New customer targeting
   - **Parameters:**
     - `campaign_type` - Type of campaign
     - `target_size` - Number of customers (default: 100)

**Example Queries (115+ Use Cases Supported):**
```
Customer Analysis:
✓ "Which customers are likely businesses?"
✓ "Show me high churn risk customers"
✓ "Who are my best customers?"
✓ "Give me an RFM analysis"
✓ "What products do my top customers prefer?"

Segment Analysis:
✓ "What types of customers do we have?"
✓ "Which segments are growing?"
✓ "How many people will shop during Halloween?"
✓ "What archetypes should we focus on this holiday season?"
✓ "Compare my top 3 customer segments"

Forecasting:
✓ "What's our revenue forecast for Q4?" (Q4 → 3 months)
✓ "How many customers will we have next year?"
✓ "Project average LTV for 6 months"
✓ "Show me churn rate trends"

Campaigns:
✓ "Who should I target for my Black Friday sale?"
✓ "Which customers should get retention offers?"
✓ "Show me customers for a loyalty program"
```

**Response Format:**
```json
{
  "query": "what archetypes should we focus on this holiday season",
  "query_type": "seasonal_archetype_recommendation",
  "answer": {
    "summary": "Focus on these 10 archetypes...",
    "top_archetypes": [
      {
        "archetype_id": "arch_650665",
        "score": 185.3,
        "total_ltv": 1316563.14,
        "member_count": 814,
        "population_percentage": 2.97,
        "dominant_segments": {...},
        "recommendation_reasons": [
          "Strong seasonal buying pattern",
          "Premium value tier",
          "High purchase frequency"
        ]
      }
    ],
    "campaign_strategy": {
      "timing": "Start campaigns 3-4 weeks before peak holiday season",
      "messaging": "Focus on gift-giving, seasonal projects, and holiday-themed products",
      "channels": "Email + retargeting ads for high-value segments",
      "offers": "Tiered discounts: 15% for premium, 20% for seasonal power buyers",
      "expected_roi": "Target segments represent $5,123,456 in lifetime value"
    },
    "aggregate_metrics": {
      "total_ltv_targeted": 5123456.78,
      "total_members_targeted": 3421,
      "avg_score": 156.4
    }
  }
}
```

**Status Codes:**
- `200 OK` - Query interpreted and routed successfully
- `500 Internal Server Error` - Analysis or AI routing failed

**Performance:**
- AI routing (Claude): ~300-500ms
- Total query time: ~1-3s (routing + analysis)
  - Seasonal recommendations: ~1.8s total
  - Churn identification: ~2.8s total
  - Revenue forecast: ~3.3s total
  - Campaign targeting: ~1.3s total

**Cost:**
- $0.00025 per query (~$2.50 per 10,000 queries)
- Uses Claude 3.5 Haiku (fastest, cheapest Claude model)

**Requirements:**
- **REQUIRED:** `ANTHROPIC_API_KEY` environment variable must be set
- Get API key from: https://console.anthropic.com/settings/keys
- Without API key: Returns error message with direct endpoint links

**Why This Approach:**
- **Infinite flexibility:** Handles any phrasing naturally with 4 flexible tools
- **Better accuracy:** Fewer tools = less confusion, B2B queries no longer default to growth campaigns
- **Scalable:** Add new analysis type = 1 parameter value + handler (not new tool)
- **Maintainable:** 4 parameterized tools handle 115+ use cases vs 20+ narrow tools
- **Robust:** Handles typos, synonyms, casual language
- **Smart extraction:** Automatically converts "Q4" → 3 months, "halloween" → event parameter
- **Context-aware:** Distinguishes "target for sale" vs "shop during" for same keywords
- **Cost-effective:** ~$0.00025 per query using Claude 3.5 Haiku

---

## MCP Tool Endpoints

### GET /api/mcp/tools

**Description:** List all available MCP tools for AI agents

**Response:**
```json
{
  "tools": [
    {
      "name": "get_customer_profile",
      "description": "Get complete behavioral profile for a customer",
      "inputSchema": {
        "type": "object",
        "properties": {
          "customer_id": {
            "type": "string",
            "description": "13-digit customer ID"
          }
        },
        "required": ["customer_id"]
      }
    },
    {
      "name": "predict_churn_risk",
      "description": "Calculate churn risk for customer",
      "inputSchema": {
        "type": "object",
        "properties": {
          "customer_id": {
            "type": "string",
            "description": "13-digit customer ID"
          }
        },
        "required": ["customer_id"]
      }
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Tools listed

---

### POST /api/mcp/query

**Description:** Execute MCP tool query (for AI agents)

**Request Body:**
```json
{
  "tool": "get_customer_profile",
  "params": {
    "customer_id": "7827249201407"
  }
}
```

**Response:** Varies by tool (same as direct endpoint calls)

**Status Codes:**
- `200 OK` - Query successful
- `400 Bad Request` - Invalid tool or params
- `500 Internal Server Error` - Query failed

---


## Response Formats

### Success Response

All successful responses include:
- Appropriate HTTP status code (200, etc.)
- JSON body with requested data
- Standard structure per endpoint

### Error Response

All errors return:
```json
{
  "detail": "Error message describing what went wrong"
}
```

Common error messages:
- `"Customer {id} not found"` - Invalid customer ID
- `"No customers loaded"` - Database not initialized
- `"Invalid metric: {metric}"` - Bad parameter value

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | When It Occurs |
|------|---------|---------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid parameters |
| 404 | Not Found | Resource (customer/archetype) not found |
| 500 | Internal Server Error | Server-side error |
| 503 | Service Unavailable | Data not loaded or system down |

### Retry Strategy

For `503` errors:
- Retry after 5 seconds
- Max 3 retries
- Exponential backoff

For `500` errors:
- Check request format
- Contact support if persists

---

## Rate Limiting

**Current:** No rate limiting implemented

**Future:** May implement:
- 100 requests per minute per IP
- 1000 requests per hour per IP
- Burst allowance: 20 requests

---

## Examples

### cURL Examples

**Get Random Customer:**
```bash
curl https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/random
```

**Get Churn Risk:**
```bash
curl https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/7827249201407/churn-risk
```

**Growth Projection:**
```bash
curl "https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/growth/projection?months=12"
```

**Top Archetypes:**
```bash
curl "https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/archetypes/top?metric=total_ltv&limit=5"
```

**Archetype Growth:**
```bash
curl "https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/archetypes/growth-projection?months=12&top_n=10"
```

---

### Python Examples

```python
import requests

BASE_URL = "https://ecommerce-backend-staging-a14c.up.railway.app"

# Get random customer
response = requests.get(f"{BASE_URL}/api/mcp/customer/random")
customer = response.json()
print(f"Customer LTV: ${customer['business_metrics']['lifetime_value']}")

# Predict churn
customer_id = customer['customer_id']
response = requests.get(f"{BASE_URL}/api/mcp/customer/{customer_id}/churn-risk")
risk = response.json()
print(f"Churn Risk: {risk['risk_level']} ({risk['churn_risk_score']*100:.1f}%)")

# Get growth projection
response = requests.get(f"{BASE_URL}/api/mcp/growth/projection", params={"months": 12})
projection = response.json()
print(f"Growth Rate: {projection['growth_rate_pct']}%")

# Top archetypes
response = requests.get(f"{BASE_URL}/api/mcp/archetypes/top", params={
    "metric": "total_ltv",
    "limit": 10
})
archetypes = response.json()
for i, arch in enumerate(archetypes['top_archetypes'][:3], 1):
    print(f"#{i}: {arch['archetype_id']} - ${arch['total_lifetime_value']:,.2f}")
```

---

### JavaScript Examples

```javascript
const BASE_URL = "https://ecommerce-backend-staging-a14c.up.railway.app";

// Get random customer
async function getRandomCustomer() {
  const response = await fetch(`${BASE_URL}/api/mcp/customer/random`);
  const customer = await response.json();
  console.log(`Customer LTV: $${customer.business_metrics.lifetime_value}`);
  return customer;
}

// Predict churn
async function predictChurn(customerId) {
  const response = await fetch(`${BASE_URL}/api/mcp/customer/${customerId}/churn-risk`);
  const risk = await response.json();
  console.log(`Risk: ${risk.risk_level} (${(risk.churn_risk_score * 100).toFixed(1)}%)`);
  return risk;
}

// Growth projection
async function getGrowthProjection(months = 12) {
  const response = await fetch(`${BASE_URL}/api/mcp/growth/projection?months=${months}`);
  const projection = await response.json();
  console.log(`Growth Rate: ${projection.growth_rate_pct}%`);
  return projection;
}

// Top archetypes
async function getTopArchetypes(metric = 'total_ltv', limit = 10) {
  const response = await fetch(
    `${BASE_URL}/api/mcp/archetypes/top?metric=${metric}&limit=${limit}`
  );
  const data = await response.json();
  data.top_archetypes.slice(0, 3).forEach((arch, i) => {
    console.log(`#${i+1}: ${arch.archetype_id} - $${arch.total_lifetime_value.toLocaleString()}`);
  });
  return data;
}

// Usage
(async () => {
  const customer = await getRandomCustomer();
  await predictChurn(customer.customer_id);
  await getGrowthProjection(12);
  await getTopArchetypes();
})();
```

---

## Versioning

**Current Version:** 1.0.0

**API Path:** No versioning in path (future: `/api/v1/...`)

**Breaking Changes:** Will be communicated via:
- GitHub releases
- Email notifications
- Deprecation warnings in responses

---

## Support

For API support:
- **Email:** scott@quimbi.ai
- **GitHub Issues:** https://github.com/Quimbi-ai/Ecommerce-backend/issues
- **Documentation:** https://github.com/Quimbi-ai/Ecommerce-backend

---

*Last Updated: 2025-10-16*
*Version: 1.0.0*
