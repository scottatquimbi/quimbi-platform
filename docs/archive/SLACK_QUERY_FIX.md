# Slack Query "Query Processed" Fix

## Problem

**User Query:** "what type of customer has the highest repeat purchases"
**Bot Response:** "Query processed" (generic, unhelpful)

## Root Cause

The query doesn't match any existing tool definitions because:

1. User is asking about **customer types/segments** ranked by **repeat purchase behavior**
2. Existing tools:
   - `query_segments` - Analyzes segments but doesn't support "repeat purchase" sorting
   - `analyze_products` - Has `category_repurchase_rate` but that's for PRODUCTS not CUSTOMERS
   - `query_customers` - Lists customers but doesn't group by segment/type

3. Claude AI can't find a matching tool, so it returns a text response with `query_type: "general_response"` but no meaningful message

4. Slack bot receives empty message, shows default: "Query processed"

## The Fix

Add the missing functionality to the `query_segments` tool:

### Option 1: Add to query_segments tool (Recommended)

Update the tool description and add new sort options:

```python
{
    "name": "query_segments",
    "description": """Analyze customer segments and archetypes - understand who your customer types are, how they behave, and how they're changing.

    Examples:
    - "What types of customers do I have?" → analysis: overview
    - "Which segments are growing?" → analysis: growth
    - "Which customer type has the highest repeat purchases?" → analysis: overview, sort_by: repurchase_rate  # NEW
    - "What segment repurchases most?" → analysis: overview, sort_by: frequency  # NEW
    """,
    "input_schema": {
        "properties": {
            "sort_by": {
                "type": "string",
                "enum": [
                    "size",           # Number of customers in segment
                    "ltv",            # Lifetime value
                    "total_revenue",  # Total segment revenue
                    "growth_rate",    # How fast segment is growing
                    "churn_rate",     # Churn risk level
                    "repurchase_rate",# NEW: Repeat purchase frequency
                    "frequency"       # NEW: Average orders per customer
                ],
                "default": "total_revenue"
            }
        }
    }
}
```

### Option 2: Update query_customers to support aggregation

Add a new scope type for segment-level aggregation:

```python
{
    "name": "query_customers",
    "description": """...""",
    "input_schema": {
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["individual", "list", "segment_summary"],  # NEW
                "description": "Query individual customer, list of customers, or aggregate by segment"
            },
            "aggregate_by": {  # NEW
                "type": "string",
                "enum": ["segment", "archetype", "behavior_pattern"],
                "description": "For scope='segment_summary': how to group customers"
            },
            "metric": {  # NEW
                "type": "string",
                "enum": ["repurchase_rate", "avg_orders", "avg_ltv", "churn_rate"],
                "description": "For scope='segment_summary': what metric to rank by"
            }
        }
    }
}
```

## Implementation

I'll implement Option 1 (simpler and more aligned with existing structure):

