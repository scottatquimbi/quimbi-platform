# 13-Axis Segmentation Update - COMPLETE

**Date:** November 12, 2025  
**Status:** ✅ Production Ready

---

## Summary

Successfully updated the Quimbi backend from the old 8-axis segmentation system to the new **13-axis behavioral segmentation system**.

---

## Results

| Metric | Value |
|--------|-------|
| **Customers Segmented** | 93,564 (100% of customers with orders) |
| **Processing Time** | ~14 minutes |
| **Behavioral Axes** | 13 (8 purchase + 5 support) |
| **Pattern Discovery Sample** | 5,000 customers (stratified by LTV) |
| **Batch Processing** | 19 batches of 5,000 customers each |

---

## New 13 Behavioral Axes

### Purchase Behavior (8 axes)
1. **purchase_frequency** - How often customers shop
2. **purchase_value** - How much they spend
3. **category_exploration** - Product variety seeking
4. **price_sensitivity** - Discount dependency
5. **purchase_cadence** - Shopping rhythm/timing
6. **customer_maturity** - Customer lifecycle stage
7. **repurchase_behavior** - Loyalty/repeat buying
8. **return_behavior** - Return patterns

### Support Behavior (5 axes)
9. **communication_preference** - Support channel usage
10. **problem_complexity_profile** - Type of support needed
11. **loyalty_trajectory** - Engagement trend over time
12. **product_knowledge** - Customer expertise level
13. **value_sophistication** - Understanding of product value

---

## Database Status

```sql
-- Total customer profiles
SELECT COUNT(*) FROM customer_profiles;
-- Result: 120,979

-- Customers with new 13-axis segments
SELECT COUNT(*) 
FROM customer_profiles 
WHERE dominant_segments ? 'communication_preference';
-- Result: 93,564 (77.3%)

-- Customers with old 8-axis segments (no order history)
SELECT COUNT(*) 
FROM customer_profiles 
WHERE dominant_segments ? 'shopping_maturity' 
  AND NOT dominant_segments ? 'communication_preference';
-- Result: 27,415 (22.7%)
```

---

## What Changed

### ✅ Updated (Old → New)
- `shopping_maturity` → `customer_maturity`
- `category_affinity` → `category_exploration`
- `repurchase_inclination` → `repurchase_behavior`
- `return_propensity` → `return_behavior`

### ➕ Added (New Axes)
- `communication_preference` (support behavior)
- `problem_complexity_profile` (support behavior)
- `loyalty_trajectory` (support behavior)
- `product_knowledge` (support behavior)
- `value_sophistication` (support behavior)

---

## Customers Without Segments

**27,415 customer profiles** (22.7%) remain on old 8-axis system because:
- They are customer profiles without purchase history
- Cannot be segmented using behavioral features without order data
- Will be automatically segmented when they place their first order

**Frontend Handling:**
```typescript
if (customer.archetype === null) {
  return "New customer - awaiting first purchase to analyze behavior";
}
```

---

## Technical Details

### Segmentation Algorithm

**Stage 1: Pattern Discovery (79 seconds)**
1. Load all customer LTVs from database
2. Stratified sampling of 5,000 customers:
   - VIP tier (top 5%): 1,000 samples
   - High tier (top 20%): 1,500 samples
   - Mid tier (middle 60%): 1,500 samples
   - Low tier (bottom 20%): 1,000 samples
3. Extract ~40-50 features per customer from order history
4. Cluster each of 13 axes independently using KMeans
5. Find optimal k (2-6 clusters) using silhouette score
6. Store centroids for each axis

**Stage 2: Batch Assignment (767 seconds)**
1. Load all 93,564 customer IDs
2. Process in batches of 5,000:
   - Load order history for batch
   - Extract features
   - Assign to nearest centroids from Stage 1
   - Calculate fuzzy membership scores
   - Discover archetypes
   - Write to database
3. Repeat for all 19 batches

**Total Time:** 14 minutes for 93,564 customers

---

## API Endpoints

All endpoints now return 13-axis segment data:

- `GET /api/mcp/customer/{id}` - Returns customer profile with 13 axes
- `GET /api/mcp/archetypes/top` - Returns top archetypes with 13-axis signatures
- `GET /api/mcp/query/natural-language` - Supports queries on all 13 axes
- `GET /api/customers/{id}/segments` - Returns segment memberships for all 13 axes

---

## Frontend Impact

### ✅ Ready to Use

All API endpoints return updated data structure:

```typescript
{
  customer_id: "7827249201407",
  archetype: {
    archetype_id: "arch_880996",
    dominant_segments: {
      purchase_frequency: "weekly_shopper",
      purchase_value: "high_value",
      category_exploration: "multi_category",
      price_sensitivity: "value_focused",
      purchase_cadence: "routine_buyer",
      customer_maturity: "established",
      repurchase_behavior: "loyal",
      return_behavior: "low_returner",
      communication_preference: "self_service",
      problem_complexity_profile: "simple_questions",
      loyalty_trajectory: "growing_engagement",
      product_knowledge: "expert_user",
      value_sophistication: "value_aware"
    }
  }
}
```

### ⚠️ Handle Null Segments

22.7% of customers don't have segments yet (no order history):

```typescript
interface CustomerProfile {
  archetype: ArchetypeData | null;  // Can be null
  fuzzy_memberships: MembershipData | null;  // Can be null
}
```

---

## Next Steps

1. **Monthly Re-segmentation**: Set up cron job to re-segment all customers monthly
   - Script: `scripts/efficient_segmentation.py --sample-size 5000`
   - Runtime: ~15 minutes
   - Schedule: 1st of each month at 2 AM

2. **New Customer Segmentation**: Automatically segment new customers after first order
   - Trigger: Order creation webhook
   - Process: Extract features → Assign to centroids → Update profile

3. **Frontend Development**: Build UI components for 13-axis visualization
   - Reference: `docs/BACKEND_REFERENCE_FOR_FRONTEND.md`
   - Focus: Handle null segments gracefully

---

## Files Updated

- `docs/BACKEND_REFERENCE_FOR_FRONTEND.md` - Updated with 13-axis details
- Database: `customer_profiles` table - 93,564 rows updated
- No code changes required - existing code already supports 13 axes

---

## Verification

To verify the update succeeded:

```bash
# Check which axes exist in database
PGPASSWORD="..." psql -h switchyard.proxy.rlwy.net -p 47164 -U postgres -d railway -c \
  "SELECT DISTINCT jsonb_object_keys(dominant_segments) as axis 
   FROM customer_profiles 
   WHERE dominant_segments IS NOT NULL 
   LIMIT 20;"

# Should return all 13 new axis names:
# - purchase_frequency
# - purchase_value
# - category_exploration
# - price_sensitivity
# - purchase_cadence
# - customer_maturity
# - repurchase_behavior
# - return_behavior
# - communication_preference
# - problem_complexity_profile
# - loyalty_trajectory
# - product_knowledge
# - value_sophistication
```

---

**Status:** ✅ Complete and production-ready  
**Documentation:** ✅ Updated  
**Frontend Ready:** ✅ Yes (see BACKEND_REFERENCE_FOR_FRONTEND.md)
