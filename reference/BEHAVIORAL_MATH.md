# Behavioral Mathematics Documentation

**System:** Multi-Axis Fuzzy Clustering for Customer Segmentation
**Author:** Quimbi Platform (E-commerce Adaptation)
**Version:** 3.0.0
**Date:** 2025-11-06

---

## Table of Contents

1. [Core Mathematical Foundations](#core-mathematical-foundations)
2. [Fuzzy Membership Calculation](#fuzzy-membership-calculation)
3. [Feature Normalization](#feature-normalization)
4. [Cluster Quality Metrics](#cluster-quality-metrics)
5. [3-Tier Archetype System](#3-tier-archetype-system)
6. [Temporal Drift Detection](#temporal-drift-detection)
7. [E-Commerce Specific Adaptations](#e-commerce-specific-adaptations)

---

## Core Mathematical Foundations

### Multi-Axis Independent Clustering

The system operates on **N independent behavioral axes**, where each axis represents a distinct dimension of customer behavior.

**Key Principle:** Axes are **statistically independent**. A customer can be:
- "High Frequency Buyer" on `purchase_frequency` axis
- "Price Sensitive" on `price_sensitivity` axis
- "Category Explorer" on `category_exploration` axis

**Mathematical Independence:**
```
P(segment_i in axis_A | segment_j in axis_B) = P(segment_i in axis_A)
```

This allows discovering natural behavioral patterns without assumptions.

---

## Fuzzy Membership Calculation

### Overview

Unlike hard clustering (each customer belongs to ONE segment), fuzzy clustering assigns **membership scores** to ALL segments.

**Core Formula:**

```python
membership[segment_i] = exp(-distance_i) / Σ exp(-distance_j)
                                           j=1 to K
```

Where:
- `distance_i` = Euclidean distance from customer to segment i's center
- `K` = number of segments in the axis
- `exp()` = exponential function (e^x)

### Step-by-Step Process

#### Step 1: Standardize Customer Features

```python
# Population-level standardization (NOT customer-level!)
customer_vector_scaled = (customer_vector - μ_population) / σ_population
```

**Critical:** Use the **same scaler** from training. This ensures:
- New customers are in the same coordinate space
- Distances are comparable across all customers

**Code Reference:** [multi_axis_clustering_engine.py:870-877](archive/backend/multi_axis_clustering_engine.py#L870-L877)

```python
# From training (stored in DiscoveredSegment)
scaler_params = {
    'mean': [μ_1, μ_2, ..., μ_n],      # Population mean per feature
    'scale': [σ_1, σ_2, ..., σ_n]      # Population std dev per feature
}

# Apply to new customer
player_vector_scaled = (player_vector - mean) / scale
```

#### Step 2: Calculate Euclidean Distances

```python
distance_i = ||customer_scaled - center_i||₂
           = sqrt(Σ (customer_j - center_i_j)²)
                  j=1 to d
```

Where:
- `d` = number of features in the axis
- `center_i` = cluster center for segment i (in scaled space)

**Code Reference:** [multi_axis_clustering_engine.py:879-883](archive/backend/multi_axis_clustering_engine.py#L879-L883)

#### Step 3: Convert Distances to Similarities

```python
similarity_i = exp(-distance_i)
```

**Why exponential decay?**
- **Close customers** (distance ≈ 0): similarity ≈ 1.0
- **Far customers** (distance >> 0): similarity ≈ 0.0
- **Smooth decay**: No hard boundaries

**Visualization:**
```
Distance:     0.0   0.5   1.0   1.5   2.0   3.0   5.0
Similarity:   1.00  0.61  0.37  0.22  0.14  0.05  0.01
```

**Code Reference:** [multi_axis_clustering_engine.py:888](archive/backend/multi_axis_clustering_engine.py#L888)

#### Step 4: Normalize to Sum = 1.0

```python
membership_i = similarity_i / Σ similarity_j
                              j=1 to K
```

**Result:** Fuzzy membership vector where:
```python
Σ membership[segment] = 1.0
segment in axis
```

**Example:**
```python
# Axis: purchase_frequency (3 segments)
distances = [0.5, 2.0, 3.5]  # Distance to each segment center

# Similarities
similarities = [exp(-0.5), exp(-2.0), exp(-3.5)]
             = [0.606, 0.135, 0.030]

# Memberships (normalized)
memberships = {
    'high_frequency': 0.606 / 0.771 = 0.786,
    'medium_frequency': 0.135 / 0.771 = 0.175,
    'low_frequency': 0.030 / 0.771 = 0.039
}

# Verify: 0.786 + 0.175 + 0.039 = 1.000 ✓
```

**Code Reference:** [multi_axis_clustering_engine.py:890-897](archive/backend/multi_axis_clustering_engine.py#L890-L897)

---

## Feature Normalization

### Why Standardize?

Different features have different scales:
- `total_orders`: Range 1-500
- `avg_order_value`: Range $10-$5000
- `days_since_last_order`: Range 0-1000

**Without standardization:** Features with large ranges dominate clustering.

### StandardScaler Formula

```python
z = (x - μ) / σ
```

Where:
- `x` = raw feature value
- `μ` = population mean
- `σ` = population standard deviation
- `z` = standardized value (z-score)

**Properties:**
- Standardized features have `mean = 0`, `std = 1`
- Preserves distribution shape
- All features contribute equally to distance calculations

**Code Reference:** [multi_axis_clustering_engine.py:564-566](archive/backend/multi_axis_clustering_engine.py#L564-L566)

```python
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # Training

# Later (inference)
customer_scaled = (customer - scaler.mean_) / scaler.scale_
```

---

## Cluster Quality Metrics

### Silhouette Score

**Purpose:** Measure how well-separated clusters are.

**Formula:**
```python
silhouette(i) = (b_i - a_i) / max(a_i, b_i)
```

Where:
- `a_i` = average distance from point i to other points in its cluster (intra-cluster)
- `b_i` = average distance from point i to points in nearest other cluster (inter-cluster)

**Range:** -1 to +1
- `> 0.5`: Strong clustering
- `0.3-0.5`: Acceptable clustering
- `< 0.3`: Weak clustering (used as minimum threshold)

**Code Reference:** [multi_axis_clustering_engine.py:648](archive/backend/multi_axis_clustering_engine.py#L648)

```python
silhouette = silhouette_score(X, labels)

if silhouette < self.min_silhouette:  # 0.3
    logger.warning("Poor clustering quality")
```

### Optimal K Selection

**Algorithm:** Try k = 2 to k = 6, choose k with highest silhouette score.

```python
best_k = argmax silhouette_score(X, KMeans(k))
         k=2 to 6
```

**Code Reference:** [multi_axis_clustering_engine.py:630-649](archive/backend/multi_axis_clustering_engine.py#L630-L649)

---

## 3-Tier Archetype System

### Level 1: Dominant Archetype (Simple)

**Purpose:** Single label for customer support agents and simple marketing.

**Formula:**
```python
dominant_archetype[axis] = argmax membership[segment]
                           segment in axis
```

**Example:**
```python
# Axis: purchase_frequency
memberships = {
    'high_frequency': 0.786,
    'medium_frequency': 0.175,
    'low_frequency': 0.039
}

dominant = 'high_frequency'  # Highest score
```

**Use Cases:**
- Customer support ticket routing
- Simple marketing segments
- Dashboard reporting

---

### Level 2: Fuzzy Archetype (868 Combinations)

**Purpose:** Multi-dimensional behavioral profile combining dominant segments across axes.

**Combinatorial Formula:**
```python
# Example: 8 axes with segments per axis
axes_segments = {
    'purchase_frequency': 3 segments,
    'purchase_value': 4 segments,
    'category_exploration': 2 segments,
    'price_sensitivity': 3 segments,
    'purchase_cadence': 4 segments,
    'customer_maturity': 3 segments,
    'repurchase_behavior': 2 segments,
    'return_behavior': 2 segments
}

total_archetypes = 3 × 4 × 2 × 3 × 4 × 3 × 2 × 2 = 3,456 possible combinations
```

**In practice:** Not all combinations exist in real data. The 868 archetypes represent **observed combinations** from the training population.

**Archetype ID Format:**
```python
archetype_id = f"{seg1}_{seg2}_{seg3}_...__{seg8}"

# Example
"high_freq_high_value_explorer_price_insensitive_regular_mature_loyal_no_returns"
```

**Stored as:**
```python
{
    'archetype_id': 'archetype_427',
    'dominant_segments': {
        'purchase_frequency': 'high_frequency',
        'purchase_value': 'high_value',
        'category_exploration': 'explorer',
        # ... (8 total)
    },
    'membership_strengths': {
        'purchase_frequency': 'strong',  # 0.786 > 0.7
        'purchase_value': 'balanced',    # 0.45 primary, 0.35 secondary
        'category_exploration': 'weak'   # No clear dominant
    },
    'segment_memberships': {
        'purchase_frequency': {
            'high_frequency': 0.786,
            'medium_frequency': 0.175,
            'low_frequency': 0.039
        },
        # ... (8 axes total)
    }
}
```

**Membership Strength Classification:**
```python
def classify_strength(memberships):
    sorted_scores = sorted(memberships.values(), reverse=True)
    primary = sorted_scores[0]
    secondary = sorted_scores[1] if len(sorted_scores) > 1 else 0.0

    if primary > 0.7:
        return 'strong'      # Clear dominant segment
    elif primary > 0.4 and secondary > 0.3:
        return 'balanced'    # Split between top 2 segments
    else:
        return 'weak'        # No clear pattern
```

**Code Reference:** [multi_axis_clustering_engine.py:289-300](archive/backend/multi_axis_clustering_engine.py#L289-L300)

**Use Cases:**
- Personalized product recommendations
- Targeted marketing campaigns
- Churn prediction models
- Customer lifetime value (LTV) estimation

---

### Level 3: Individual Fingerprint (Quasi 1:1)

**Purpose:** Unique behavioral signature for each customer, enabling hyper-personalization.

**Concept:** Store **distance to ALL segment centers** across ALL axes.

**Data Structure:**
```python
{
    'customer_id': 'C12345',
    'behavioral_fingerprint': {
        'purchase_frequency': {
            'high_frequency': {
                'distance': 0.5,
                'membership': 0.786
            },
            'medium_frequency': {
                'distance': 2.0,
                'membership': 0.175
            },
            'low_frequency': {
                'distance': 3.5,
                'membership': 0.039
            }
        },
        # ... (8 axes × ~3 segments/axis = 24 distance measurements)
    },

    # Flattened vector for k-NN
    'distance_vector': [0.5, 2.0, 3.5, 1.2, 0.8, ...],  # Length ≈ 24-32

    'archetype_l2_id': 'archetype_427'  # Reference to Level 2
}
```

**K-Nearest Neighbors (k-NN) Recommendations:**
```python
# Find k most similar customers
def find_similar_customers(target_customer_id, k=10):
    target_vector = fingerprints[target_customer_id]['distance_vector']

    similarities = []
    for customer_id, data in fingerprints.items():
        if customer_id == target_customer_id:
            continue

        # Cosine similarity
        similarity = cosine_similarity(target_vector, data['distance_vector'])
        similarities.append((customer_id, similarity))

    # Return top k
    return sorted(similarities, key=lambda x: x[1], reverse=True)[:k]
```

**Use Cases:**
- "Customers like you also bought..."
- Next-best-action recommendations
- Lookalike audience targeting
- Anomaly detection (behavioral drift)

**Database Schema:**
```sql
-- Stored in customer_profiles.segment_memberships (JSONB)
{
    "purchase_frequency": {
        "high_frequency": 0.786,
        "medium_frequency": 0.175,
        "low_frequency": 0.039
    },
    "purchase_value": {
        "high_value": 0.654,
        "medium_value": 0.287,
        "low_value": 0.059
    }
    -- ... (8 axes)
}
```

---

## Temporal Drift Detection

### Multi-Resolution Snapshots

**Purpose:** Track how customers' behavioral profiles change over time.

**Snapshot Intervals:**
```python
snapshot_intervals = [
    7,     # 1 week ago
    14,    # 2 weeks ago
    28,    # 4 weeks ago
    60,    # ~2 months ago
    90,    # 3 months ago
    180    # 6 months ago
]
```

**Database Schema:**
```sql
CREATE TABLE fact_customer_history (
    snapshot_id UUID PRIMARY KEY,
    customer_id VARCHAR(100),
    snapshot_date TIMESTAMP,
    days_ago INT,  -- 7, 14, 28, 60, 90, 180

    -- Snapshot of customer_profiles at that time
    archetype_l2_id VARCHAR(50),
    segment_memberships JSONB,
    dominant_segments JSONB,

    -- Business metrics
    lifetime_value FLOAT,
    total_orders INT,
    churn_risk_score FLOAT
);
```

**Code Reference:** [alembic/versions/2025_10_16_hybrid_star_schema.py](alembic/versions/2025_10_16_hybrid_star_schema.py)

---

### Drift Velocity Calculation

**Concept:** Measure rate of change in customer behavior.

**Formula:**
```python
drift_velocity[axis] = Δ membership / Δ time
```

**Example:**
```python
# purchase_frequency axis
current = {
    'high_frequency': 0.786,
    'medium_frequency': 0.175,
    'low_frequency': 0.039
}

snapshot_14d_ago = {
    'high_frequency': 0.920,
    'medium_frequency': 0.065,
    'low_frequency': 0.015
}

# Calculate drift
drift = {
    'high_frequency': (0.786 - 0.920) / 14 = -0.0096 per day,
    'medium_frequency': (0.175 - 0.065) / 14 = +0.0079 per day,
    'low_frequency': (0.039 - 0.015) / 14 = +0.0017 per day
}

# Interpretation: Customer is drifting FROM high_frequency TO medium_frequency
```

**Drift Magnitude (L2 Norm):**
```python
drift_magnitude = sqrt(Σ (Δ membership_i)²)
                       i

# Example
drift_magnitude = sqrt((-0.134)² + (0.110)² + (0.024)²)
                = sqrt(0.01796 + 0.0121 + 0.000576)
                = sqrt(0.030436)
                = 0.174

# Normalized per day
drift_velocity = 0.174 / 14 days = 0.0124 per day
```

**Thresholds:**
```python
if drift_velocity > 0.015:
    alert = 'RAPID_DRIFT'  # Customer behavior changing quickly
elif drift_velocity > 0.008:
    alert = 'MODERATE_DRIFT'
else:
    alert = 'STABLE'
```

---

### Archetype Migration Detection

**Concept:** Detect when customer's dominant archetype changes.

**Formula:**
```python
migration = (archetype_current != archetype_previous)
```

**Example:**
```python
# Current (today)
current_archetype = 'archetype_427'
dominant_segments_current = {
    'purchase_frequency': 'high_frequency',
    'purchase_value': 'high_value'
}

# Snapshot (28 days ago)
previous_archetype = 'archetype_189'
dominant_segments_previous = {
    'purchase_frequency': 'high_frequency',
    'purchase_value': 'medium_value'
}

# Detect migration
if current_archetype != previous_archetype:
    # Identify which axes changed
    axes_changed = []
    for axis in dominant_segments_current:
        if dominant_segments_current[axis] != dominant_segments_previous[axis]:
            axes_changed.append({
                'axis': axis,
                'from': dominant_segments_previous[axis],
                'to': dominant_segments_current[axis]
            })

    # Result
    migration = {
        'migrated': True,
        'from_archetype': 'archetype_189',
        'to_archetype': 'archetype_427',
        'axes_changed': [
            {'axis': 'purchase_value', 'from': 'medium_value', 'to': 'high_value'}
        ],
        'migration_date': '2025-11-06',
        'days_elapsed': 28
    }
```

**Business Interpretation:**
```
Customer C12345 has upgraded from medium-value to high-value purchases
over the past 28 days. Consider:
- Upsell premium products
- Offer VIP tier benefits
- Increase engagement campaigns
```

**Churn Risk Detection:**
```python
# High-value customer drifting to low engagement
if (
    previous['purchase_frequency'] == 'high_frequency' and
    current['purchase_frequency'] == 'medium_frequency' and
    drift_velocity > 0.010
):
    churn_risk = 'HIGH'

    # Trigger intervention
    actions = [
        'Send re-engagement email',
        'Offer 15% discount',
        'Customer success call'
    ]
```

---

### Trend Analysis (Multi-Period)

**Purpose:** Detect long-term vs short-term behavioral changes.

**Formula:**
```python
# Short-term trend (7-day vs 14-day)
short_term_drift = memberships_7d - memberships_14d

# Long-term trend (90-day vs 180-day)
long_term_drift = memberships_90d - memberships_180d

# Acceleration (is drift accelerating or decelerating?)
acceleration = short_term_drift - long_term_drift
```

**Example:**
```python
snapshots = {
    '7d':  {'high_frequency': 0.786, 'medium_frequency': 0.175},
    '14d': {'high_frequency': 0.820, 'medium_frequency': 0.140},
    '28d': {'high_frequency': 0.875, 'medium_frequency': 0.105},
    '90d': {'high_frequency': 0.920, 'medium_frequency': 0.065},
    '180d': {'high_frequency': 0.935, 'medium_frequency': 0.052}
}

# Short-term drift (7d → 14d)
short_drift = 0.786 - 0.820 = -0.034 (decreasing high_frequency)

# Long-term drift (90d → 180d)
long_drift = 0.920 - 0.935 = -0.015 (slower decrease)

# Interpretation: Customer's frequency is declining, and the decline is ACCELERATING
```

**Visualization:**
```
Membership Score
1.0 |
    |                                    * (180d ago)
0.9 |                               *       * (90d ago)
    |                          *                * (28d ago)
0.8 |                     *                          * (14d ago)
    |                *                                     * (7d ago, current)
0.7 |_______________________________________________________________
    0d          50d         100d        150d        200d

    Trend: Declining high_frequency membership
    Velocity: Accelerating (slope steepening)
    Alert: CHURN_RISK_HIGH
```

---

## E-Commerce Specific Adaptations

### Axis Definitions (Gaming → E-Commerce)

#### Marketing-Focused Axes (1-8)

| Gaming Axis | E-Commerce Equivalent | Key Features |
|-------------|----------------------|--------------|
| `feature_engagement` | `category_exploration` | `unique_categories`, `category_switches`, `new_category_rate` |
| `temporal_patterns` | `purchase_cadence` | `weekend_vs_weekday`, `time_of_day_consistency`, `seasonal_pattern` |
| `intensity_patterns` | `purchase_frequency` | `orders_per_month`, `avg_days_between_orders`, `purchase_consistency` |
| `progression_velocity` | `customer_maturity` | `tenure_months`, `orders_per_tenure`, `expansion_rate` |
| `content_consumption` | `purchase_value` | `avg_order_value`, `lifetime_value`, `value_trend` |
| `learning_curve` | `price_sensitivity` | `discount_usage_rate`, `avg_discount_pct`, `full_price_ratio` |
| `volatility` | `repurchase_behavior` | `repeat_purchase_rate`, `same_product_rate`, `loyalty_index` |
| NEW | `return_behavior` | `return_rate`, `return_reasons`, `return_value_ratio` |

#### Support-Focused Axes (9-14)

| Axis | Name | Key Features | Use Case |
|------|------|--------------|----------|
| 9 | `communication_preference` | `primary_channel`, `preferred_contact_time`, `channel_diversity` | Ticket routing, callback scheduling |
| 10 | `problem_complexity_profile` | `refund_rate`, `return_frequency`, `discount_dependency` | Senior agent routing, proactive support |
| 11 | `loyalty_trajectory` | `order_frequency_trend`, `churn_risk`, `acceleration_phase` | Churn prevention, retention campaigns |
| 12 | `product_knowledge` | `product_concentration`, `repeat_product_rate`, `expertise_level` | Response complexity, education targeting |
| 13 | `value_sophistication` | `price_point_comfort`, `discount_hunt_score`, `luxury_rate` | Price dispute handling, promotion targeting |
| 14 | `support_history` | `tickets_per_order`, `satisfaction_avg`, `escalation_rate` | Agent matching, proactive outreach |

**Total System:** 14 behavioral axes (8 marketing + 6 support)

**Data Sources:**
- Axes 1-13: Order history only (available NOW)
- Axis 14: Requires Gorgias ticket history storage

**Detailed Analysis:** [SUPPORT_AXES_ANALYSIS.md](SUPPORT_AXES_ANALYSIS.md)

**Code Reference:** [IMPLEMENTATION_STATUS_REPORT.md](IMPLEMENTATION_STATUS_REPORT.md#e-commerce-axes)

---

### RFM Integration

**Concept:** RFM (Recency, Frequency, Monetary) metrics are FEATURES in multiple axes.

```python
# purchase_frequency axis
features = {
    'orders_per_month': total_orders / tenure_months,  # F (Frequency)
    'avg_days_between_orders': mean(gaps),
    'recent_orders_90d': count(orders in last 90 days),  # R (Recency)
}

# purchase_value axis
features = {
    'avg_order_value': total_value / total_orders,  # M (Monetary)
    'lifetime_value': sum(order_values),
    'value_trend': linear_regression(order_values over time)
}
```

**Why Multi-Axis is Better than Traditional RFM:**

| Traditional RFM | Multi-Axis Fuzzy |
|----------------|------------------|
| 3 dimensions (R, F, M) | 8 dimensions (behavioral axes) |
| Hard segments (e.g., "111" high-high-high) | Fuzzy memberships (0-1 continuous) |
| Equal weighting | Axes weighted by business importance |
| No temporal tracking | Multi-resolution drift detection |
| Static snapshot | Dynamic behavioral fingerprint |

---

### AI Segment Naming

**Requirement:** Segment names should be **generated by AI after clustering**, not hardcoded.

**Current (Gaming) Code:**
```python
# WRONG: Hardcoded gaming names
segment_name = 'weekend_warrior'
segment_name = 'binge_player'
```

**Correct (E-Commerce) Approach:**

**Step 1: Cluster and Extract Centroids**
```python
# After KMeans clustering
cluster_center_original = scaler.inverse_transform(cluster_center_scaled)

# Get feature values
features = {
    'orders_per_month': cluster_center_original[0],
    'avg_days_between_orders': cluster_center_original[1],
    'recent_orders_90d': cluster_center_original[2],
    'purchase_consistency': cluster_center_original[3]
}
```

**Step 2: Call Claude API for Naming**
```python
async def name_segment_with_ai(axis_name, cluster_center, feature_names, population_stats):
    """
    Use Claude API to generate human-readable segment name.

    Args:
        axis_name: e.g., 'purchase_frequency'
        cluster_center: [2.5, 15.3, 8.2, 0.73]
        feature_names: ['orders_per_month', 'avg_days_between_orders', ...]
        population_stats: {'orders_per_month': {'min': 0.5, 'max': 12, 'median': 2.1}}
    """

    # Build prompt
    prompt = f"""
    I've discovered a customer segment in the '{axis_name}' behavioral dimension.

    Cluster center features:
    {format_features(cluster_center, feature_names)}

    Population statistics:
    {format_population_stats(population_stats)}

    Generate:
    1. A concise segment name (2-4 words, snake_case)
    2. A 1-sentence interpretation

    Examples:
    - high_frequency_loyalists
    - occasional_browsers
    - seasonal_shoppers

    Respond in JSON format.
    """

    response = await anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": prompt}]
    )

    result = json.loads(response.content[0].text)

    return {
        'segment_name': result['segment_name'],
        'interpretation': result['interpretation']
    }
```

**Step 3: Validate and Store**
```python
# Ensure uniqueness
if segment_name in existing_names:
    segment_name = f"{segment_name}_{cluster_id}"

# Store
segment = DiscoveredSegment(
    segment_id=f"{game_id}_{axis_name}_{segment_name}",
    segment_name=segment_name,
    interpretation=interpretation,
    # ...
)
```

**Benefits:**
- Names reflect actual data patterns
- No hardcoded assumptions
- Generalizes to any vertical (gaming, e-commerce, SaaS, etc.)
- Human-readable for business users

**Code Implementation Location:**
```python
# backend/segmentation/ai_segment_naming.py (TO BE CREATED)
```

---

## Summary of Key Formulas

### Fuzzy Membership
```python
membership_i = exp(-||customer - center_i||) / Σ exp(-||customer - center_j||)
```

### Feature Standardization
```python
z = (x - μ_population) / σ_population
```

### Euclidean Distance
```python
d = sqrt(Σ (customer_j - center_j)²)
```

### Silhouette Score
```python
s = (b - a) / max(a, b)
```

### Drift Velocity
```python
v = ||memberships_current - memberships_previous|| / Δt
```

### Archetype Migration
```python
migrated = (archetype_current != archetype_previous)
```

---

## Implementation Status

**Current State:**
- ✅ Mathematical formulas defined and coded (in archive/)
- ✅ Database schema created (JSONB columns for fuzzy memberships)
- ❌ Multi-axis engine ARCHIVED (gaming code, not adapted)
- ❌ Fuzzy memberships NOT calculated (JSONB columns empty)
- ❌ Temporal drift tracking NOT implemented (snapshots not created)
- ❌ AI segment naming NOT implemented

**Next Steps:**
1. Adapt multi_axis_clustering_engine.py from gaming to e-commerce
2. Create EcommerceFeatureExtractor (8 axes)
3. Run initial clustering on 27,415 customers
4. Populate customer_profiles.segment_memberships (JSONB)
5. Implement weekly snapshot job (fact_customer_history)
6. Implement AI segment naming via Claude API
7. Build drift detection and alerting

**Reference:** [IMPLEMENTATION_STATUS_REPORT.md](IMPLEMENTATION_STATUS_REPORT.md)

---

## References

**Code:**
- [archive/backend/multi_axis_clustering_engine.py](archive/backend/multi_axis_clustering_engine.py)
- [archive/backend/multi_axis_feature_extraction.py](archive/backend/multi_axis_feature_extraction.py)
- [alembic/versions/2025_10_15_ecommerce_vectors.py](alembic/versions/2025_10_15_ecommerce_vectors.py)
- [alembic/versions/2025_10_16_hybrid_star_schema.py](alembic/versions/2025_10_16_hybrid_star_schema.py)

**Documentation:**
- [IMPLEMENTATION_STATUS_REPORT.md](IMPLEMENTATION_STATUS_REPORT.md)
- [ML_ARCHITECTURE_DEEP_DIVE.md](ML_ARCHITECTURE_DEEP_DIVE.md)
- [STRATEGIC_ANALYSIS_CORRECTION.md](STRATEGIC_ANALYSIS_CORRECTION.md)

**Libraries:**
- scikit-learn: `StandardScaler`, `KMeans`, `silhouette_score`
- numpy: `exp()`, `linalg.norm()`, array operations
- scipy: `cosine_similarity`, `cdist`

---

**Last Updated:** 2025-11-06
**Status:** Reference documentation for implementation
**Author:** Reconstructed from gaming code + user specifications
