# Customer Support Behavioral Axes

**Date:** 2025-11-06
**Purpose:** Additional behavioral axes specifically designed for customer support operations
**Data Source:** Linda's order history + Gorgias ticket data

---

## Available Data Fields

### From Orders Table
```python
# Order-level
'OrderID', 'Customer_ID', 'Date_Customer', 'Date_Financial', 'TotalPrice',
'ItemQTY', 'Source', 'TotalDiscount', 'Sales', 'QTY'

# Product-level (per order line item)
'ProductId', 'Category', 'ProductType', 'Refunds'

# Channels
'Source': ['pos', 'web', 'shopify_draft_order']
```

### From Gorgias (if available)
```python
# Ticket data
'ticket_id', 'customer_id', 'created_at', 'status', 'priority',
'channel', 'subject', 'tags', 'agent_id', 'response_time',
'resolution_time', 'satisfaction_score'
```

---

## Proposed Support-Specific Axes

### Axis 9: Communication Preference
**Purpose:** How customers prefer to interact and their responsiveness

**Features to Extract:**
```python
{
    # Channel preference
    'primary_purchase_channel': 'web' | 'pos' | 'shopify_draft_order',
    'channel_diversity': 1-3,  # How many channels they use
    'channel_switching_rate': 0.0-1.0,  # How often they switch channels

    # Time patterns (for support contact timing)
    'preferred_contact_time': 'morning' | 'afternoon' | 'evening',
    'weekend_vs_weekday_ratio': 0.0-5.0,  # > 1 = prefers weekends
    'business_hours_ratio': 0.0-1.0,  # Pct of activity during business hours

    # Order placement behavior (proxy for communication style)
    'avg_order_complexity': 1.0-50.0,  # Avg items per order
    'custom_order_rate': 0.0-1.0,  # Pct of draft orders (suggests phone/custom)
}
```

**Business Value:**
- **Route tickets to agents available during customer's preferred time**
- **Match communication channel** (phone-preferring customers get calls, not emails)
- **Predict response rate** (business hours customers respond faster during work hours)

**Segment Examples:**
- `digital_native` - 100% web, business hours, simple orders
- `personal_shopper` - High custom orders, phone/POS, complex requests
- `omnichannel_flexible` - Uses all channels, no strong preference
- `weekend_warrior` - Only shops/contacts on weekends

---

### Axis 10: Problem Complexity Profile
**Purpose:** How complex/problematic are this customer's purchases

**Features to Extract:**
```python
{
    # Return/Refund behavior
    'refund_rate': 0.0-1.0,  # Total refunds / lifetime value
    'items_returned_pct': 0.0-1.0,  # Items returned / items purchased
    'return_frequency': 0.0-5.0,  # Returns per month
    'return_value_ratio': 0.0-2.0,  # Avg return value / avg order value

    # Order changes/cancellations (if available)
    'order_change_rate': 0.0-1.0,  # How often orders are modified

    # Product issues proxy
    'unique_products_vs_orders': 0.5-5.0,  # High = trying many products (may signal dissatisfaction)
    'category_switching_rate': 0.0-1.0,  # Frequent switches = searching for right fit

    # Discount dependency (price dispute proxy)
    'discount_dependency': 0.0-1.0,  # Pct orders with discount
    'discount_amount_avg': $0-$100,  # How much discount they expect
}
```

**Business Value:**
- **Pre-emptive support** - High return customers get proactive "how can we help?" messages
- **Agent assignment** - Complex profiles go to senior agents
- **Product recommendations** - Help customers find right products first time
- **Fraud detection** - Unusual return patterns flagged

**Segment Examples:**
- `low_maintenance` - No returns, simple orders, no issues
- `high_touch_shopper` - Frequent returns, tries many products, needs guidance
- `price_sensitive_returner` - Returns unless discounted, may dispute charges
- `fit_finder` - Switches categories, trying to find right product match
- `problematic_pattern` - High returns + high value + frequent complaints (fraud risk)

---

### Axis 11: Loyalty & Engagement Trajectory
**Purpose:** Is customer becoming MORE or LESS engaged over time?

**Features to Extract:**
```python
{
    # Engagement velocity
    'order_frequency_trend': -1.0 to +1.0,  # Linear regression slope of orders/month over time
    'value_trend': -1.0 to +1.0,  # Is spending increasing or decreasing?
    'recency_momentum': -1.0 to +1.0,  # Are gaps between orders getting shorter or longer?

    # Lifecycle stage
    'customer_maturity': 0-5,  # 0=new, 5=mature (based on tenure + orders)
    'acceleration_phase': bool,  # Recently increased frequency (last 3 months vs prior 3)
    'deceleration_phase': bool,  # Recently decreased frequency

    # Stability
    'purchase_consistency': 0.0-1.0,  # Inverse of std dev of gaps between orders
    'seasonal_buyer': bool,  # Only buys during certain quarters
    'expected_next_purchase_days': 1-365,  # Based on historical pattern

    # Expansion
    'category_expansion_rate': 0.0-1.0,  # Rate of trying new categories over time
    'value_expansion_rate': 0.0-2.0,  # AOV growth rate
}
```

**Business Value:**
- **Churn prediction** - Deceleration phase customers get retention offers
- **Upsell timing** - Acceleration phase customers receptive to premium products
- **Proactive engagement** - Contact customers BEFORE expected churn
- **Win-back campaigns** - Target customers who've gone silent

**Segment Examples:**
- `accelerating_loyalist` - Increasing frequency + value, expanding categories
- `stable_regular` - Consistent orders, predictable pattern
- `declining_risk` - Decreasing frequency, longer gaps, churn warning
- `seasonal_stable` - Predictable quarterly purchases, not churned just seasonal
- `new_explorer` - Recent customer, still figuring out what they like
- `plateaued_mature` - Long tenure but flat spending, needs re-engagement

---

### Axis 12: Product Knowledge & Expertise
**Purpose:** How much guidance does the customer need?

**Features to Extract:**
```python
{
    # Browsing behavior proxy
    'product_concentration': 0.0-1.0,  # Herfindahl index (low = diverse explorer)
    'repeat_product_rate': 0.0-1.0,  # Same products reordered
    'new_product_trial_rate': 0.0-1.0,  # Pct of orders with never-bought-before items

    # Category expertise
    'primary_category_dominance': 0.0-1.0,  # How much they focus on one category
    'categories_mastered': 0-10,  # Categories with 3+ repeat purchases

    # Decision speed proxy
    'avg_time_between_first_last_purchase': 1-1000,  # Fast = knows what they want
    'order_size_consistency': 0.0-1.0,  # Consistent sizes = routine buyer

    # Product type diversity
    'unique_product_types': 1-50,
    'unique_products_per_order': 1.0-20.0,  # High = exploratory shopping
}
```

**Business Value:**
- **Content targeting** - Experts get advanced tips, beginners get basic guides
- **Support ticket routing** - Beginners to patient educators, experts to specialists
- **Product recommendations** - Explorers get variety, loyalists get similar items
- **Educational content** - Target learning materials to expertise level

**Segment Examples:**
- `category_expert` - Deep knowledge in 1-2 categories, repeat buyer
- `curious_explorer` - Tries many products, diverse orders, learning phase
- `routine_reorderer` - Same products every time, knows exactly what they want
- `impulse_experimenter` - Random product mix, no clear pattern
- `niche_specialist` - Very focused on specific product type

---

### Axis 13: Value & Spend Sophistication
**Purpose:** How do customers perceive and extract value?

**Features to Extract:**
```python
{
    # Price point comfort
    'avg_price_point': $0-$500,  # Avg item price (not order total)
    'price_point_variance': 0.0-1.0,  # Consistent vs varying price ranges
    'luxury_item_rate': 0.0-1.0,  # Pct items in top 20% price range
    'budget_item_rate': 0.0-1.0,  # Pct items in bottom 20% price range

    # Value extraction
    'items_per_dollar': 0.01-2.0,  # QTY / total spent (high = bargain hunter)
    'discount_hunt_score': 0.0-1.0,  # Always buys on discount
    'full_price_comfort': 0.0-1.0,  # Willing to pay full price

    # Spend patterns
    'spend_consistency': 0.0-1.0,  # Similar order values
    'big_splurge_rate': 0.0-0.5,  # Pct orders >2x avg (special occasions)
    'basket_building': 0.0-1.0,  # Orders items together vs one-at-a-time
}
```

**Business Value:**
- **Pricing disputes** - Discount hunters may complain about prices
- **Promotional targeting** - Send discounts to price-sensitive, not luxury buyers
- **Product positioning** - Frame value differently for each segment
- **Upsell strategy** - Luxury buyers receptive to premium, budget buyers need value proof

**Segment Examples:**
- `luxury_buyer` - High price points, full price purchases, consistent premium
- `value_optimizer` - Mid-price, strategic discount use, quality-conscious
- `bargain_hunter` - Only buys on sale, high items-per-dollar
- `occasion_splurger` - Normally budget, occasional big orders (gifts?)
- `price_indifferent` - No discount pattern, wide price variance

---

### Axis 14: Support Interaction History (Requires Gorgias Data)
**Purpose:** Past support behavior predicts future needs

**Features to Extract (if Gorgias integrated):**
```python
{
    # Ticket frequency
    'tickets_per_order': 0.0-2.0,  # Support intensity
    'proactive_contact_rate': 0.0-1.0,  # Contacts before problems vs reactive

    # Issue types
    'shipping_issues_rate': 0.0-1.0,  # Pct tickets about shipping
    'product_question_rate': 0.0-1.0,  # Pct tickets about products
    'return_request_rate': 0.0-1.0,  # Pct tickets for returns
    'complaint_rate': 0.0-1.0,  # Pct negative sentiment tickets

    # Resolution behavior
    'avg_response_time_hours': 0-168,  # How fast they respond to agents
    'escalation_rate': 0.0-1.0,  # Pct tickets escalated
    'satisfaction_avg': 1.0-5.0,  # CSAT scores
    'repeat_issue_rate': 0.0-1.0,  # Same problem multiple times

    # Communication style
    'message_length_avg': 10-500,  # Word count
    'follow_up_rate': 0.0-5.0,  # Avg follow-ups per ticket
    'self_service_rate': 0.0-1.0,  # Resolved via help docs vs agent
}
```

**Business Value:**
- **Proactive support** - High-ticket customers get check-in messages
- **Agent matching** - Difficult customers to experienced agents
- **Self-service targeting** - Push help docs to self-servers, personal touch to others
- **Issue prediction** - Shipping issue customers get proactive tracking updates

**Segment Examples:**
- `low_touch_self_solver` - Rarely contacts, uses help docs, quick responses
- `high_touch_hand_holder` - Frequent contact, needs reassurance
- `chronic_complainer` - High complaint rate, low satisfaction, escalations
- `product_guru` - Only contacts with complex product questions
- `logistics_worried` - Always asks about shipping/tracking

**Note:** This axis requires Gorgias webhook data to be historical and stored.

---

## Implementation Priority for Support

### Phase 1: Order Data Only (No Gorgias Required)

**High Priority (Implement First):**
1. **Axis 11: Loyalty & Engagement Trajectory**
   - Identifies churn risk
   - Enables proactive support
   - Data available NOW

2. **Axis 10: Problem Complexity Profile**
   - Flags high-return/problematic customers
   - Routes complex cases to senior agents
   - Data available NOW

3. **Axis 9: Communication Preference**
   - Optimizes support contact timing/channel
   - Data available NOW

**Medium Priority:**
4. **Axis 12: Product Knowledge & Expertise**
   - Helps tailor support response complexity
   - Data available NOW

5. **Axis 13: Value & Spend Sophistication**
   - Predicts price disputes
   - Data available NOW

### Phase 2: Enhanced with Gorgias Integration

6. **Axis 14: Support Interaction History**
   - Requires storing Gorgias ticket history
   - Needs webhook data retention (not just real-time)
   - High value but requires infrastructure

---

## Support Use Cases by Axis

### Use Case 1: Intelligent Ticket Routing

**Decision Logic:**
```python
def route_ticket(customer_profile):
    # High complexity → Senior agent
    if customer_profile['problem_complexity_segment'] == 'high_touch_shopper':
        return 'senior_agent_queue'

    # Churn risk → Retention specialist
    if customer_profile['loyalty_trajectory_segment'] == 'declining_risk':
        return 'retention_specialist'

    # Product expert → Technical specialist
    if customer_profile['product_knowledge_segment'] == 'category_expert':
        return 'product_specialist'

    # Default
    return 'general_support'
```

**Axes Used:** 10, 11, 12

---

### Use Case 2: Proactive Support Outreach

**Trigger Logic:**
```python
def proactive_outreach_candidates():
    candidates = []

    for customer in customers:
        # Deceleration phase + high historical value
        if (customer['loyalty_trajectory_segment'] == 'declining_risk' and
            customer['lifetime_value'] > 500):
            candidates.append({
                'customer_id': customer.id,
                'message': 'We noticed you haven\'t ordered recently. How can we help?',
                'priority': 'high'
            })

        # High return rate on recent orders
        if (customer['problem_complexity_segment'] == 'high_touch_shopper' and
            customer['recent_return_rate_3mo'] > 0.5):
            candidates.append({
                'customer_id': customer.id,
                'message': 'We see some recent returns. Let\'s help you find the perfect products.',
                'priority': 'medium'
            })

    return candidates
```

**Axes Used:** 10, 11, 13

---

### Use Case 3: Personalized Response Templates

**Template Selection:**
```python
def get_response_template(customer_profile, issue_type):
    # Expert customer + product question
    if (customer_profile['product_knowledge_segment'] == 'category_expert' and
        issue_type == 'product_question'):
        return 'technical_detailed_response'

    # Beginner + product question
    if (customer_profile['product_knowledge_segment'] == 'curious_explorer' and
        issue_type == 'product_question'):
        return 'educational_basic_response'

    # Discount hunter + price complaint
    if (customer_profile['value_segment'] == 'bargain_hunter' and
        issue_type == 'price_inquiry'):
        return 'value_focused_response'  # Emphasize quality + upcoming sales

    # Luxury buyer + price complaint
    if (customer_profile['value_segment'] == 'luxury_buyer' and
        issue_type == 'price_inquiry'):
        return 'premium_service_response'  # Emphasize exclusivity + service
```

**Axes Used:** 12, 13

---

### Use Case 4: Expected Contact Time Optimization

**Schedule Callbacks:**
```python
def schedule_callback(customer_profile):
    comm_pref = customer_profile['communication_preference']

    # Weekend warrior → Schedule for Saturday morning
    if comm_pref['weekend_vs_weekday_ratio'] > 2.0:
        return 'saturday_9am'

    # Business hours buyer → Schedule workday afternoon
    if comm_pref['business_hours_ratio'] > 0.8:
        return 'weekday_2pm'

    # Evening buyer → Schedule after hours
    if comm_pref['preferred_contact_time'] == 'evening':
        return 'weekday_6pm'
```

**Axes Used:** 9

---

### Use Case 5: Churn Prevention Workflow

**Multi-Axis Risk Score:**
```python
def calculate_churn_risk(customer_profile):
    risk_score = 0

    # Loyalty trajectory (40% weight)
    if customer_profile['loyalty_trajectory_segment'] == 'declining_risk':
        risk_score += 40
    elif customer_profile['loyalty_trajectory_segment'] == 'plateaued_mature':
        risk_score += 20

    # Problem complexity (30% weight)
    if customer_profile['problem_complexity_segment'] == 'high_touch_shopper':
        risk_score += 30
    elif customer_profile['refund_rate'] > 0.3:
        risk_score += 20

    # Engagement (30% weight)
    days_since_last = customer_profile['days_since_last_purchase']
    expected_days = customer_profile['expected_next_purchase_days']

    if days_since_last > expected_days * 1.5:
        risk_score += 30
    elif days_since_last > expected_days:
        risk_score += 15

    # Classification
    if risk_score >= 70:
        return 'HIGH_RISK'
    elif risk_score >= 40:
        return 'MEDIUM_RISK'
    else:
        return 'LOW_RISK'
```

**Axes Used:** 10, 11

**Actions by Risk Level:**
- **HIGH_RISK:** Personal phone call from account manager + 20% discount
- **MEDIUM_RISK:** Personalized email + new product recommendations
- **LOW_RISK:** Standard newsletter

---

## Feature Engineering Examples

### Axis 9: Communication Preference

```python
def extract_communication_preference(orders):
    """Extract communication preference features from order history."""

    # Channel analysis
    channel_counts = orders['Source'].value_counts()
    primary_channel = channel_counts.index[0]
    channel_diversity = len(channel_counts)

    # Calculate channel switching
    orders_sorted = orders.sort_values('Date_Customer')
    channel_switches = (orders_sorted['Source'] != orders_sorted['Source'].shift()).sum() - 1
    channel_switching_rate = channel_switches / len(orders) if len(orders) > 1 else 0

    # Time patterns
    orders['hour'] = orders['Date_Customer'].dt.hour
    orders['is_weekend'] = orders['Date_Customer'].dt.dayofweek >= 5
    orders['is_business_hours'] = orders['hour'].between(9, 17)

    morning_orders = (orders['hour'] < 12).sum()
    afternoon_orders = orders['hour'].between(12, 17).sum()
    evening_orders = (orders['hour'] >= 17).sum()

    preferred_time = 'morning' if morning_orders == max([morning_orders, afternoon_orders, evening_orders]) \
                     else ('afternoon' if afternoon_orders > evening_orders else 'evening')

    weekend_ratio = orders['is_weekend'].sum() / (len(orders) - orders['is_weekend'].sum() or 1)
    business_hours_ratio = orders['is_business_hours'].mean()

    # Order complexity
    avg_order_complexity = orders['ItemQTY'].mean()
    custom_order_rate = (orders['Source'] == 'shopify_draft_order').mean()

    return {
        'primary_purchase_channel': primary_channel,
        'channel_diversity': channel_diversity,
        'channel_switching_rate': channel_switching_rate,
        'preferred_contact_time': preferred_time,
        'weekend_vs_weekday_ratio': weekend_ratio,
        'business_hours_ratio': business_hours_ratio,
        'avg_order_complexity': avg_order_complexity,
        'custom_order_rate': custom_order_rate
    }
```

### Axis 10: Problem Complexity Profile

```python
def extract_problem_complexity(orders, items, reference_date):
    """Extract problem complexity features."""

    # Return/refund metrics
    total_refunds = items['Refunds'].fillna(0).sum()
    lifetime_value = orders['TotalPrice'].sum()
    refund_rate = total_refunds / lifetime_value if lifetime_value > 0 else 0

    items_returned = (items['Refunds'].fillna(0) > 0).sum()
    total_items = len(items)
    items_returned_pct = items_returned / total_items if total_items > 0 else 0

    # Return frequency (returns per month)
    tenure_months = (reference_date - orders['Date_Customer'].min()).days / 30.44
    return_frequency = items_returned / tenure_months if tenure_months > 0 else 0

    # Product exploration as issue proxy
    unique_products = items['ProductId'].nunique()
    total_orders = len(orders)
    unique_products_vs_orders = unique_products / total_orders if total_orders > 0 else 0

    # Category switching
    category_orders = items.groupby('Category').size()
    category_switches = len(category_orders)
    category_switching_rate = category_switches / total_orders if total_orders > 0 else 0

    # Discount dependency
    orders_with_discount = (orders['TotalDiscount'] > 0).sum()
    discount_dependency = orders_with_discount / total_orders if total_orders > 0 else 0
    discount_amount_avg = orders[orders['TotalDiscount'] > 0]['TotalDiscount'].mean() or 0

    return {
        'refund_rate': refund_rate,
        'items_returned_pct': items_returned_pct,
        'return_frequency': return_frequency,
        'unique_products_vs_orders': unique_products_vs_orders,
        'category_switching_rate': category_switching_rate,
        'discount_dependency': discount_dependency,
        'discount_amount_avg': discount_amount_avg
    }
```

### Axis 11: Loyalty & Engagement Trajectory

```python
def extract_loyalty_trajectory(orders, reference_date):
    """Extract loyalty trajectory features."""
    import numpy as np
    from scipy import stats

    orders_sorted = orders.sort_values('Date_Customer')

    # Calculate order frequency trend (linear regression)
    if len(orders) >= 3:
        # Create time series: months since first order
        first_order = orders_sorted['Date_Customer'].iloc[0]
        orders_sorted['months_since_first'] = (
            (orders_sorted['Date_Customer'] - first_order).dt.days / 30.44
        )

        # Count orders per month bucket
        max_months = orders_sorted['months_since_first'].max()
        month_buckets = np.arange(0, max_months + 1)
        orders_per_month = []

        for month in month_buckets:
            count = ((orders_sorted['months_since_first'] >= month) &
                     (orders_sorted['months_since_first'] < month + 1)).sum()
            orders_per_month.append(count)

        # Linear regression: y = orders/month, x = month
        if len(month_buckets) >= 2:
            slope, intercept, r_value, p_value, std_err = stats.linregress(
                month_buckets, orders_per_month
            )
            order_frequency_trend = slope
        else:
            order_frequency_trend = 0
    else:
        order_frequency_trend = 0

    # Value trend
    if len(orders) >= 3:
        value_slope, _, _, _, _ = stats.linregress(
            range(len(orders)),
            orders_sorted['TotalPrice'].values
        )
        value_trend = np.sign(value_slope)
    else:
        value_trend = 0

    # Recency momentum (are gaps getting shorter or longer?)
    if len(orders) >= 3:
        gaps = orders_sorted['Date_Customer'].diff().dt.days.dropna()
        if len(gaps) >= 2:
            gap_slope, _, _, _, _ = stats.linregress(range(len(gaps)), gaps.values)
            recency_momentum = -np.sign(gap_slope)  # Negative gap slope = getting faster
        else:
            recency_momentum = 0
    else:
        recency_momentum = 0

    # Customer maturity (0-5 scale)
    tenure_months = (reference_date - orders['Date_Customer'].min()).days / 30.44
    total_orders = len(orders)

    maturity_score = 0
    if tenure_months >= 24: maturity_score += 2
    elif tenure_months >= 12: maturity_score += 1

    if total_orders >= 20: maturity_score += 3
    elif total_orders >= 10: maturity_score += 2
    elif total_orders >= 5: maturity_score += 1

    customer_maturity = min(maturity_score, 5)

    # Acceleration/deceleration phase
    recent_90d = orders[orders['Date_Customer'] >= reference_date - pd.Timedelta(days=90)]
    prior_90d = orders[(orders['Date_Customer'] >= reference_date - pd.Timedelta(days=180)) &
                       (orders['Date_Customer'] < reference_date - pd.Timedelta(days=90))]

    recent_orders_per_month = len(recent_90d) / 3
    prior_orders_per_month = len(prior_90d) / 3 if len(prior_90d) > 0 else 0

    acceleration_phase = recent_orders_per_month > prior_orders_per_month * 1.5
    deceleration_phase = recent_orders_per_month < prior_orders_per_month * 0.5

    # Purchase consistency
    if len(orders) >= 2:
        gaps = orders_sorted['Date_Customer'].diff().dt.days.dropna()
        consistency = 1.0 / (1.0 + gaps.std()) if len(gaps) > 0 else 0
    else:
        consistency = 0

    # Expected next purchase
    if len(orders) >= 2:
        avg_gap = gaps.mean()
        expected_next_purchase_days = int(avg_gap)
    else:
        expected_next_purchase_days = 365

    return {
        'order_frequency_trend': order_frequency_trend,
        'value_trend': value_trend,
        'recency_momentum': recency_momentum,
        'customer_maturity': customer_maturity,
        'acceleration_phase': acceleration_phase,
        'deceleration_phase': deceleration_phase,
        'purchase_consistency': consistency,
        'expected_next_purchase_days': expected_next_purchase_days
    }
```

---

## Summary

### Total Axes: 14 (8 Marketing + 6 Support)

**Marketing-Focused (Axes 1-8):**
1. Purchase Frequency
2. Purchase Value
3. Category Exploration
4. Price Sensitivity
5. Purchase Cadence
6. Customer Maturity
7. Repurchase Behavior
8. Return Behavior

**Support-Focused (Axes 9-14):**
9. **Communication Preference** - Channel, timing, contact style
10. **Problem Complexity Profile** - Returns, issues, complexity
11. **Loyalty & Engagement Trajectory** - Churn risk, lifecycle stage
12. **Product Knowledge & Expertise** - Guidance needed
13. **Value & Spend Sophistication** - Price disputes, value perception
14. **Support Interaction History** - Past tickets (requires Gorgias)

### Implementation Recommendation

**Start with Axes 9-11** (all use existing order data):
- Immediate value for support team
- No additional data sources needed
- Enables intelligent ticket routing
- Powers proactive churn prevention

**Add Axes 12-13** next:
- Enhances support response personalization
- Further refines ticket routing

**Add Axis 14** when Gorgias history is stored:
- Requires infrastructure to persist ticket data
- Highest support-specific value
- Enables learning from past interactions

---

**All support axes can be implemented using existing Linda order data except Axis 14.**

**Combined system: 8 marketing axes + 5 support axes = 13 axes operational immediately.**
