# Frontend Reference Documentation

**Last Updated:** November 13, 2025

This folder contains all the essential documentation needed for frontend development of the Quimbi Customer Intelligence Platform.

---

## Quick Start - Read These First

1. **[BACKEND_REFERENCE_FOR_FRONTEND.md](./BACKEND_REFERENCE_FOR_FRONTEND.md)** ⭐ **START HERE**
   - Complete guide to understanding the Quimbi backend
   - The math behind behavioral segmentation
   - TypeScript interfaces for all data structures
   - React integration examples
   - Common use cases and patterns

2. **[SEGMENTATION_UPDATE_COMPLETE.md](./SEGMENTATION_UPDATE_COMPLETE.md)**
   - Current system status (13-axis segmentation)
   - Database statistics and verification
   - Frontend impact and null handling requirements
   - Production-ready status confirmation

3. **[API_DOCUMENTATION.md](./API_DOCUMENTATION.md)**
   - Complete API endpoint reference
   - Request/response examples
   - Error handling
   - Rate limits and best practices

---

## Architecture & Design

4. **[ARCHITECTURE.md](./ARCHITECTURE.md)**
   - System architecture overview
   - Component relationships
   - Data flow diagrams
   - Tech stack details

5. **[BEHAVIORAL_SEGMENTATION.md](./BEHAVIORAL_SEGMENTATION.md)**
   - Deep dive into segmentation logic
   - Clustering algorithm details
   - Feature extraction process

6. **[AUTHENTICATION.md](./AUTHENTICATION.md)**
   - API authentication setup
   - API key management
   - Security best practices

---

## Key Concepts Summary

### What is Quimbi?

A Customer Intelligence Platform that analyzes e-commerce purchase behavior to:
- Segment customers into behavioral groups (archetypes) based on 13 axes
- Predict churn risk
- Forecast LTV and growth trends
- Generate insights via natural language AI queries
- Automate customer support with behavioral context

### The 13 Behavioral Axes

**Purchase Behavior (8 axes):**
1. purchase_frequency - How often they shop
2. purchase_value - How much they spend
3. category_exploration - Product variety seeking
4. price_sensitivity - Discount dependency
5. purchase_cadence - Shopping rhythm/timing
6. customer_maturity - Customer lifecycle stage
7. repurchase_behavior - Loyalty/repeat buying
8. return_behavior - Return patterns

**Support Behavior (5 axes):**
9. communication_preference - Support channel usage
10. problem_complexity_profile - Type of support needed
11. loyalty_trajectory - Engagement trend over time
12. product_knowledge - Customer expertise level
13. value_sophistication - Understanding of product value

### Current System Status

- **93,564 customers** actively segmented (customers with purchase history)
- **27,415 customers** awaiting first order (will be segmented automatically)
- **13 behavioral axes** in production
- **Dynamic archetype discovery** via KMeans clustering
- **Fuzzy membership scores** for all segments (0-100% membership)

---

## Frontend Requirements

### Must Handle Null Segments

22.7% of customers don't have segments yet (no order history):

```typescript
interface CustomerProfile {
  archetype: ArchetypeData | null;  // Can be null
  fuzzy_memberships: MembershipData | null;  // Can be null
}

// Check before displaying
if (customer.archetype === null) {
  return "New customer - awaiting first purchase to analyze behavior";
}
```

### Display Priorities

1. **Customer Card**
   - LTV tier badge (VIP/High/Standard/Low)
   - Churn risk indicator (color-coded)
   - Archetype name if available
   - Key behavioral traits

2. **Archetype Details**
   - All 13 dominant segments
   - Population percentage
   - Member count
   - Average metrics (LTV, orders, churn)

3. **Behavioral Profile**
   - Radar chart or heatmap of fuzzy memberships
   - Timeline of engagement/loyalty trajectory
   - Support preferences (channel, complexity)

---

## API Endpoints Quick Reference

### Core Endpoints

```bash
# Get customer profile with full segmentation data
GET /api/mcp/customer/{customer_id}

# Get customer order history
GET /api/mcp/customer/{customer_id}/orders

# Get top archetypes by population or LTV
GET /api/mcp/archetypes/top?limit=10&sort_by=ltv

# Natural language query (AI-powered)
POST /api/mcp/query/natural-language
Body: { "query": "show me high-value customers at risk of churning" }

# Aggregate churn analysis
GET /api/mcp/churn/aggregate

# Get segment statistics for an axis
GET /api/customers/segments/statistics?axis=purchase_frequency
```

### Authentication

All requests require API key header:
```
X-API-Key: your_admin_key_here
```

---

## TypeScript Types

```typescript
interface CustomerProfile {
  customer_id: string;
  archetype: {
    archetype_id: string;
    dominant_segments: {
      purchase_frequency: string;
      purchase_value: string;
      category_exploration: string;
      price_sensitivity: string;
      purchase_cadence: string;
      customer_maturity: string;
      repurchase_behavior: string;
      return_behavior: string;
      communication_preference: string;
      problem_complexity_profile: string;
      loyalty_trajectory: string;
      product_knowledge: string;
      value_sophistication: string;
    };
    member_count: number;
    population_percentage: number;
  } | null;
  fuzzy_memberships: {
    [axis: string]: {
      [segment: string]: number;
    };
  } | null;
  business_metrics: {
    lifetime_value: number;
    total_orders: number;
    avg_order_value: number;
    days_since_last_purchase: number | null;
    customer_tenure_days: number;
  };
  churn_risk?: {
    risk_level: "critical" | "high" | "medium" | "low";
    churn_risk_score: number;
    factors: object;
    recommendation: string;
  };
}
```

---

## Common Use Cases

### 1. Display Customer Card
```typescript
const CustomerCard = ({ customerId }: { customerId: string }) => {
  const { data: customer } = useQuery(
    ['customer', customerId],
    () => fetch(`/api/mcp/customer/${customerId}`).then(r => r.json())
  );

  if (!customer) return <Loading />;

  return (
    <Card>
      <LTVBadge value={customer.business_metrics.lifetime_value} />
      {customer.churn_risk && (
        <ChurnIndicator level={customer.churn_risk.risk_level} />
      )}
      {customer.archetype ? (
        <ArchetypeName>{customer.archetype.archetype_id}</ArchetypeName>
      ) : (
        <Badge>New Customer - No orders yet</Badge>
      )}
    </Card>
  );
};
```

### 2. Browse Top Archetypes
```typescript
const ArchetypeList = () => {
  const { data: archetypes } = useQuery('top-archetypes', () =>
    fetch('/api/mcp/archetypes/top?limit=20&sort_by=ltv').then(r => r.json())
  );

  return archetypes?.map(archetype => (
    <ArchetypeCard key={archetype.archetype_id}>
      <h3>{archetype.segment_name}</h3>
      <p>{archetype.member_count} customers ({archetype.population_percentage}%)</p>
      <p>Avg LTV: ${archetype.avg_lifetime_value}</p>
    </ArchetypeCard>
  ));
};
```

### 3. Natural Language Search
```typescript
const CustomerSearch = () => {
  const [query, setQuery] = useState('');
  const { mutate, data } = useMutation(
    (q: string) => fetch('/api/mcp/query/natural-language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q })
    }).then(r => r.json())
  );

  return (
    <div>
      <SearchInput
        value={query}
        onChange={e => setQuery(e.target.value)}
        onSubmit={() => mutate(query)}
        placeholder="e.g., show me VIP customers who haven't ordered in 60 days"
      />
      <ResultsList results={data?.results} />
    </div>
  );
};
```

---

## Development Workflow

1. **Read BACKEND_REFERENCE_FOR_FRONTEND.md** - Understand the system
2. **Review API_DOCUMENTATION.md** - Learn the endpoints
3. **Check SEGMENTATION_UPDATE_COMPLETE.md** - Verify current status
4. **Build frontend** using provided TypeScript interfaces
5. **Test with API** using authentication headers
6. **Handle null segments** gracefully for new customers

---

## Support & Questions

For backend implementation questions, refer to:
- Main codebase: `/backend` directory
- Feature extraction: `/backend/segmentation/ecommerce_feature_extraction.py`
- Clustering engine: `/backend/segmentation/ecommerce_clustering_engine.py`
- API routers: `/backend/api/routers/`

---

**Status:** ✅ All documentation current as of November 13, 2025
**Backend:** ✅ Production-ready with 13-axis segmentation
**Frontend:** 🔨 Ready to build
