# Clustering Algorithm Enhancement Plan
## Preserving Original While Adding Advanced Features

**Goal**: Enhance Quimbi's behavioral clustering with temporal snapshots, drift detection, and improvements while keeping the original algorithm intact as a fallback.

---

## 🎯 Core Principle: Backwards Compatibility

All enhancements will be:
1. ✅ **Feature-flagged** - Can be enabled/disabled per tenant
2. ✅ **Non-breaking** - Original API responses unchanged
3. ✅ **Incremental** - New features added alongside existing ones
4. ✅ **Reversible** - Can roll back to original algorithm anytime

---

## 📦 Phase 1: Temporal Snapshots (Foundation)
**Timeline**: Week 1-2
**Risk**: Low
**Dependencies**: None

### 1.1 Database Schema (New Tables Only)

```sql
-- New table: Customer profile snapshots
CREATE TABLE IF NOT EXISTS platform.customer_profile_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id BIGINT NOT NULL,
    store_id VARCHAR NOT NULL,
    snapshot_date DATE NOT NULL,
    snapshot_type VARCHAR(20) NOT NULL,  -- 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'

    -- Profile data at snapshot time (frozen copy)
    archetype_id UUID,
    archetype_level INT,
    archetype_name VARCHAR(255),
    dominant_segments JSONB,              -- {axis: segment_name}
    fuzzy_memberships JSONB,              -- {axis: {segment: membership_score}}
    behavioral_features JSONB,            -- Raw feature values per axis

    -- ML predictions at snapshot time
    churn_risk_score FLOAT,
    churn_risk_level VARCHAR(20),
    predicted_ltv FLOAT,

    -- Context metadata
    orders_at_snapshot INT,
    total_value_at_snapshot NUMERIC(10,2),
    days_since_first_order INT,
    tenure_months FLOAT,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    data_version VARCHAR(20) DEFAULT 'v1.0',  -- Track schema changes

    CONSTRAINT unique_customer_snapshot UNIQUE (customer_id, snapshot_date, snapshot_type)
);

-- Indexes
CREATE INDEX idx_snapshots_customer_date ON platform.customer_profile_snapshots(customer_id, snapshot_date DESC);
CREATE INDEX idx_snapshots_date_type ON platform.customer_profile_snapshots(snapshot_date, snapshot_type);
CREATE INDEX idx_snapshots_store ON platform.customer_profile_snapshots(store_id);
CREATE INDEX idx_snapshots_archetype ON platform.customer_profile_snapshots(archetype_id);

-- Partition by month for performance (optional, for scale)
-- ALTER TABLE platform.customer_profile_snapshots
-- PARTITION BY RANGE (snapshot_date);
```

### 1.2 Snapshot Service (New Module)

**File**: `backend/services/snapshot_service.py`

```python
"""
Customer Profile Snapshot Service

Handles creation, storage, and retrieval of temporal customer snapshots.
Does NOT modify existing clustering logic.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SnapshotConfig:
    """Configuration for snapshot intervals"""
    daily_retention_days: int = 7
    weekly_retention_days: int = 60
    monthly_retention_days: int = 365
    quarterly_retention_years: int = 2
    yearly_retention_years: int = 5

    # Feature flags
    enabled: bool = True
    snapshot_on_profile_change: bool = False  # Trigger snapshot when profile changes significantly


class CustomerSnapshotService:
    """
    Manages temporal snapshots of customer profiles.

    Responsibilities:
        - Create snapshots at scheduled intervals
        - Retrieve historical snapshots
        - Prune old snapshots per retention policy
        - Does NOT modify customer profiling logic
    """

    def __init__(self, db_session, config: Optional[SnapshotConfig] = None):
        self.db_session = db_session
        self.config = config or SnapshotConfig()

    async def create_snapshot(
        self,
        customer_id: str,
        store_id: str,
        snapshot_type: str,
        profile_data: Dict[str, Any]
    ) -> str:
        """
        Create a snapshot from current customer profile.

        Args:
            customer_id: Customer identifier
            store_id: Store identifier
            snapshot_type: 'daily', 'weekly', 'monthly', etc.
            profile_data: Current profile from customer_profiles table

        Returns:
            snapshot_id (UUID)
        """
        if not self.config.enabled:
            logger.debug(f"Snapshots disabled, skipping for customer {customer_id}")
            return None

        snapshot_date = datetime.now().date()

        # Check if snapshot already exists (idempotent)
        existing = await self._get_snapshot(customer_id, snapshot_date, snapshot_type)
        if existing:
            logger.debug(f"Snapshot already exists for {customer_id} on {snapshot_date}")
            return existing['snapshot_id']

        # Insert snapshot (frozen copy of current state)
        snapshot = {
            'customer_id': customer_id,
            'store_id': store_id,
            'snapshot_date': snapshot_date,
            'snapshot_type': snapshot_type,
            'archetype_id': profile_data.get('archetype_id'),
            'archetype_level': profile_data.get('archetype_level'),
            'archetype_name': profile_data.get('archetype_name'),
            'dominant_segments': profile_data.get('dominant_segments'),
            'fuzzy_memberships': profile_data.get('fuzzy_memberships'),
            'behavioral_features': profile_data.get('behavioral_features'),
            'churn_risk_score': profile_data.get('churn_risk_score'),
            'churn_risk_level': profile_data.get('churn_risk_level'),
            'predicted_ltv': profile_data.get('predicted_ltv'),
            'orders_at_snapshot': profile_data.get('total_orders'),
            'total_value_at_snapshot': profile_data.get('lifetime_value'),
            'days_since_first_order': profile_data.get('days_since_first_order'),
            'tenure_months': profile_data.get('tenure_months')
        }

        snapshot_id = await self._insert_snapshot(snapshot)
        logger.info(f"Created {snapshot_type} snapshot for customer {customer_id}: {snapshot_id}")

        return snapshot_id

    async def get_customer_history(
        self,
        customer_id: str,
        days: int = 28,
        snapshot_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get customer's snapshot history.

        Args:
            customer_id: Customer identifier
            days: Number of days to look back
            snapshot_type: Filter by type (None = all types)

        Returns:
            List of snapshots, ordered by date DESC
        """
        # Implementation details...
        pass

    async def prune_old_snapshots(self):
        """
        Remove snapshots older than retention policy.

        Retention rules:
            - Daily: Keep 7 days
            - Weekly: Keep 60 days
            - Monthly: Keep 365 days
            - Quarterly: Keep 2 years
            - Yearly: Keep 5 years
        """
        # Implementation details...
        pass
```

### 1.3 Snapshot Creation Cron Job

**File**: `backend/jobs/create_snapshots_job.py`

```python
"""
Daily Snapshot Creation Job

Runs daily at 3 AM (after nightly Azure sync at 2 AM).
Creates snapshots for all active customers.
"""

import asyncio
from datetime import datetime
import logging

from backend.services.snapshot_service import CustomerSnapshotService, SnapshotConfig
from backend.core.database import get_db_session
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def create_daily_snapshots():
    """
    Create snapshots for all active customers.

    Snapshot types created:
        - Daily: Every day
        - Weekly: Every Monday
        - Monthly: 1st of each month
        - Quarterly: Jan 1, Apr 1, Jul 1, Oct 1
        - Yearly: Jan 1
    """
    logger.info("Starting daily snapshot creation job")

    async with get_db_session() as session:
        snapshot_service = CustomerSnapshotService(session)

        # Get all customers with profiles
        result = await session.execute(text("""
            SELECT
                customer_id,
                store_id,
                archetype_id,
                archetype_level,
                dominant_segments,
                fuzzy_memberships,
                behavioral_features,
                churn_risk_score,
                predicted_ltv
            FROM platform.customer_profiles
            WHERE updated_at >= NOW() - INTERVAL '30 days'  -- Active in last 30 days
        """))

        customers = result.fetchall()
        logger.info(f"Found {len(customers)} active customers")

        # Determine which snapshot types to create today
        snapshot_types = ['daily']

        today = datetime.now()
        if today.weekday() == 0:  # Monday
            snapshot_types.append('weekly')
        if today.day == 1:  # First of month
            snapshot_types.append('monthly')
        if today.month in [1, 4, 7, 10] and today.day == 1:  # Quarterly
            snapshot_types.append('quarterly')
        if today.month == 1 and today.day == 1:  # Yearly
            snapshot_types.append('yearly')

        logger.info(f"Creating snapshot types: {snapshot_types}")

        # Create snapshots
        created_count = 0
        for customer in customers:
            profile_data = {
                'archetype_id': customer.archetype_id,
                'archetype_level': customer.archetype_level,
                'dominant_segments': customer.dominant_segments,
                'fuzzy_memberships': customer.fuzzy_memberships,
                'behavioral_features': customer.behavioral_features,
                'churn_risk_score': customer.churn_risk_score,
                'predicted_ltv': customer.predicted_ltv
            }

            for snapshot_type in snapshot_types:
                await snapshot_service.create_snapshot(
                    customer_id=str(customer.customer_id),
                    store_id=customer.store_id,
                    snapshot_type=snapshot_type,
                    profile_data=profile_data
                )
                created_count += 1

        logger.info(f"Created {created_count} snapshots")

        # Prune old snapshots
        await snapshot_service.prune_old_snapshots()
        logger.info("Snapshot pruning complete")


async def main():
    """Entry point for cron job"""
    try:
        await create_daily_snapshots()
        logger.info("✅ Snapshot job completed successfully")
    except Exception as e:
        logger.error(f"❌ Snapshot job failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
```

### 1.4 Add to Railway Cron (Existing Service)

**File**: `packages/intelligence/railway.toml` (update)

```toml
# Add new cron job for snapshots
[[deploy.cron]]
schedule = "0 3 * * *"  # 3 AM UTC daily (after Azure sync)
command = "python -m backend.jobs.create_snapshots_job"
```

---

## 📊 Phase 2: Drift Detection & Analysis
**Timeline**: Week 3-4
**Risk**: Low
**Dependencies**: Phase 1 (snapshots must exist)

### 2.1 Drift Analysis Service (New Module)

**File**: `backend/services/drift_analysis_service.py`

```python
"""
Customer Drift Analysis Service

Analyzes temporal changes in customer behavior using snapshots.
Completely separate from core clustering algorithm.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class SegmentTransition:
    """A transition between segments on an axis"""
    axis: str
    from_segment: str
    to_segment: str
    date: datetime
    membership_change: float  # How much membership shifted


@dataclass
class AxisDrift:
    """Drift analysis for one behavioral axis"""
    axis: str
    drift_score: float  # 0-1 (Euclidean distance in membership space)
    direction: str  # 'improving', 'degrading', 'stable'
    velocity: float  # drift per day
    transitions: List[SegmentTransition]


@dataclass
class CustomerDriftAnalysis:
    """Complete drift analysis for a customer"""
    customer_id: str
    store_id: str
    analysis_window: str  # '7d', '28d', '6m', '1y'
    start_date: datetime
    end_date: datetime

    # Overall metrics
    overall_drift: float  # Average drift across all axes
    drift_velocity: float  # Overall drift per day

    # Per-axis drift
    axis_drift: Dict[str, AxisDrift]  # {axis_name: AxisDrift}

    # Archetype journey
    archetype_transitions: List[Tuple[str, datetime]]  # [(archetype_name, date), ...]

    # Anomalies detected
    anomalies: List[Dict[str, Any]]

    # Trend predictions
    predicted_30d_drift: float
    churn_risk_trend: str  # 'increasing', 'decreasing', 'stable'

    # Recommendations
    recommendations: List[str]


class DriftAnalysisService:
    """
    Analyzes customer behavioral drift over time.

    Uses temporal snapshots to detect:
        - Segment transitions (axis-level changes)
        - Drift magnitude and velocity
        - Anomalies (sudden changes)
        - Trends (improving vs degrading)
    """

    def __init__(self, db_session):
        self.db_session = db_session

    async def analyze_customer_drift(
        self,
        customer_id: str,
        window_days: int = 28
    ) -> CustomerDriftAnalysis:
        """
        Analyze customer's behavioral drift over time window.

        Args:
            customer_id: Customer identifier
            window_days: Analysis window (7, 28, 180, 365)

        Returns:
            CustomerDriftAnalysis with all metrics
        """
        # Get snapshots for time window
        snapshots = await self._get_snapshots(customer_id, window_days)

        if len(snapshots) < 2:
            logger.warning(f"Insufficient snapshots for drift analysis: {len(snapshots)}")
            return None

        # Calculate drift per axis
        axis_drift = {}
        for axis in self._get_all_axes(snapshots):
            drift = self._calculate_axis_drift(snapshots, axis)
            axis_drift[axis] = drift

        # Overall drift (average across axes)
        overall_drift = np.mean([d.drift_score for d in axis_drift.values()])

        # Velocity (drift per day)
        days_span = (snapshots[-1]['snapshot_date'] - snapshots[0]['snapshot_date']).days
        drift_velocity = overall_drift / days_span if days_span > 0 else 0

        # Detect anomalies
        anomalies = self._detect_anomalies(snapshots)

        # Archetype transitions
        archetype_transitions = self._track_archetype_journey(snapshots)

        # Churn risk trend
        churn_risk_trend = self._analyze_churn_trend(snapshots)

        # Generate recommendations
        recommendations = self._generate_recommendations(axis_drift, churn_risk_trend)

        return CustomerDriftAnalysis(
            customer_id=customer_id,
            store_id=snapshots[0]['store_id'],
            analysis_window=f"{window_days}d",
            start_date=snapshots[0]['snapshot_date'],
            end_date=snapshots[-1]['snapshot_date'],
            overall_drift=overall_drift,
            drift_velocity=drift_velocity,
            axis_drift=axis_drift,
            archetype_transitions=archetype_transitions,
            anomalies=anomalies,
            predicted_30d_drift=0.0,  # TODO: ML prediction
            churn_risk_trend=churn_risk_trend,
            recommendations=recommendations
        )

    def _calculate_axis_drift(
        self,
        snapshots: List[Dict],
        axis: str
    ) -> AxisDrift:
        """
        Calculate drift for one behavioral axis.

        Uses Euclidean distance in fuzzy membership space:
            drift = sqrt(Σ (membership_t1[seg] - membership_t0[seg])^2)
        """
        if len(snapshots) < 2:
            return AxisDrift(axis=axis, drift_score=0, direction='stable', velocity=0, transitions=[])

        # Get memberships at t0 and t1
        t0 = snapshots[0]
        t1 = snapshots[-1]

        memberships_t0 = t0.get('fuzzy_memberships', {}).get(axis, {})
        memberships_t1 = t1.get('fuzzy_memberships', {}).get(axis, {})

        # Calculate Euclidean distance
        all_segments = set(memberships_t0.keys()) | set(memberships_t1.keys())
        distance_squared = 0.0

        for segment in all_segments:
            m0 = memberships_t0.get(segment, 0.0)
            m1 = memberships_t1.get(segment, 0.0)
            distance_squared += (m1 - m0) ** 2

        drift_score = np.sqrt(distance_squared)

        # Normalize to 0-1 (max possible distance is sqrt(2) for binary membership)
        drift_score = min(drift_score / np.sqrt(2), 1.0)

        # Detect transitions
        transitions = self._detect_transitions(snapshots, axis)

        # Determine direction (improving vs degrading)
        direction = self._classify_direction(t0, t1, axis)

        # Calculate velocity
        days_span = (t1['snapshot_date'] - t0['snapshot_date']).days
        velocity = drift_score / days_span if days_span > 0 else 0

        return AxisDrift(
            axis=axis,
            drift_score=drift_score,
            direction=direction,
            velocity=velocity,
            transitions=transitions
        )

    def _detect_anomalies(self, snapshots: List[Dict]) -> List[Dict[str, Any]]:
        """
        Detect behavioral anomalies.

        Anomalies:
            1. Sudden drift (>0.5 change in 7 days)
            2. Reversals (A→B→A within 28 days)
            3. Velocity spikes (drift rate 3x baseline)
        """
        anomalies = []

        # Calculate rolling drift between consecutive snapshots
        for i in range(1, len(snapshots)):
            t0 = snapshots[i-1]
            t1 = snapshots[i]
            days_gap = (t1['snapshot_date'] - t0['snapshot_date']).days

            # Check each axis
            for axis in self._get_all_axes([t0, t1]):
                drift = self._calculate_single_drift(t0, t1, axis)

                # Anomaly 1: Sudden large drift
                if drift > 0.5 and days_gap <= 7:
                    anomalies.append({
                        'type': 'sudden_drift',
                        'axis': axis,
                        'date': t1['snapshot_date'],
                        'severity': drift,
                        'description': f'Large behavioral change ({drift:.2f}) in {days_gap} days'
                    })

        return anomalies

    def _generate_recommendations(
        self,
        axis_drift: Dict[str, AxisDrift],
        churn_risk_trend: str
    ) -> List[str]:
        """Generate actionable recommendations based on drift analysis"""
        recommendations = []

        # Check for degrading axes
        for axis, drift in axis_drift.items():
            if drift.direction == 'degrading' and drift.drift_score > 0.3:
                if axis == 'purchase_frequency':
                    recommendations.append(
                        "Send re-engagement campaign - purchase frequency declining"
                    )
                elif axis == 'purchase_value':
                    recommendations.append(
                        "Offer upsell/cross-sell - average order value declining"
                    )
                elif axis == 'loyalty_trajectory':
                    recommendations.append(
                        "High-touch outreach - loyalty trajectory negative"
                    )

        # Churn risk trending up
        if churn_risk_trend == 'increasing':
            recommendations.append(
                "Priority retention campaign - churn risk increasing"
            )

        return recommendations
```

### 2.2 New API Endpoints

**File**: `backend/api/routers/customers.py` (add to existing)

```python
@router.get("/{customer_id}/drift")
async def get_customer_drift(
    customer_id: str,
    window: str = "28d",  # 7d, 28d, 90d, 180d, 365d
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get customer's behavioral drift analysis.

    NEW ENDPOINT - Does not affect existing /customers/{id} endpoint.
    """
    # Parse window
    window_days = int(window.replace('d', ''))

    # Get drift analysis
    drift_service = DriftAnalysisService(db)
    analysis = await drift_service.analyze_customer_drift(customer_id, window_days)

    if not analysis:
        raise HTTPException(status_code=404, detail="Insufficient data for drift analysis")

    return {
        "customer_id": customer_id,
        "analysis_window": analysis.analysis_window,
        "overall_drift": analysis.overall_drift,
        "drift_velocity": analysis.drift_velocity,
        "axis_drift": {
            axis: {
                "drift_score": drift.drift_score,
                "direction": drift.direction,
                "velocity": drift.velocity,
                "transitions": [
                    {
                        "from": t.from_segment,
                        "to": t.to_segment,
                        "date": t.date.isoformat()
                    }
                    for t in drift.transitions
                ]
            }
            for axis, drift in analysis.axis_drift.items()
        },
        "archetype_journey": [
            {"archetype": name, "date": date.isoformat()}
            for name, date in analysis.archetype_transitions
        ],
        "anomalies": analysis.anomalies,
        "churn_risk_trend": analysis.churn_risk_trend,
        "recommendations": analysis.recommendations
    }


@router.get("/{customer_id}/history")
async def get_customer_history(
    customer_id: str,
    days: int = 28,
    snapshot_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get customer's profile history (snapshots).

    NEW ENDPOINT - Provides raw temporal data.
    """
    snapshot_service = CustomerSnapshotService(db)
    snapshots = await snapshot_service.get_customer_history(
        customer_id,
        days=days,
        snapshot_type=snapshot_type
    )

    return {
        "customer_id": customer_id,
        "snapshots": snapshots
    }
```

---

## 🔧 Phase 3: Algorithm Improvements (Optional Enhancements)
**Timeline**: Week 5-6
**Risk**: Medium (requires testing)
**Dependencies**: Phase 1, 2

### 3.1 Outlier Detection (New Feature, Non-Breaking)

**File**: `backend/segmentation/outlier_detection.py` (NEW)

```python
"""
Outlier Detection for Customer Profiles

Identifies customers with abnormal behavior patterns.
Completely separate from core clustering - can be disabled.
"""

from typing import Dict, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class OutlierAnalysis:
    """Outlier analysis result"""
    is_outlier: bool
    outlier_score: float  # 0-1 (1 = extreme outlier)
    outlier_axes: List[str]  # Axes where customer is outlier
    explanation: str


class OutlierDetector:
    """
    Detects outliers using isolation from cluster centers.

    Method: If customer has low membership in ALL segments on an axis,
    they're an outlier on that axis.
    """

    def __init__(self, outlier_threshold: float = 0.7):
        """
        Args:
            outlier_threshold: Min outlier score to flag (0-1)
        """
        self.outlier_threshold = outlier_threshold

    def detect_outliers(
        self,
        fuzzy_memberships: Dict[str, Dict[str, float]]
    ) -> OutlierAnalysis:
        """
        Detect if customer is an outlier based on fuzzy memberships.

        Logic:
            - For each axis, find max membership score
            - If max membership < 0.3, customer is outlier on that axis
            - Overall outlier score = 1 - avg(max_memberships)
        """
        outlier_axes = []
        max_memberships = []

        for axis, memberships in fuzzy_memberships.items():
            max_membership = max(memberships.values()) if memberships else 0
            max_memberships.append(max_membership)

            # Low membership in all segments = outlier
            if max_membership < 0.3:
                outlier_axes.append(axis)

        # Overall outlier score
        avg_max_membership = np.mean(max_memberships) if max_memberships else 0
        outlier_score = 1.0 - avg_max_membership

        is_outlier = outlier_score >= self.outlier_threshold

        # Generate explanation
        if is_outlier:
            explanation = f"Customer shows unusual behavior on {len(outlier_axes)} axes: {', '.join(outlier_axes)}"
        else:
            explanation = "Customer fits discovered behavioral patterns"

        return OutlierAnalysis(
            is_outlier=is_outlier,
            outlier_score=outlier_score,
            outlier_axes=outlier_axes,
            explanation=explanation
        )
```

**Integration** (optional, feature-flagged):

```python
# In ecommerce_clustering_engine.py
# Add to calculate_customer_profile() method

if self.enable_outlier_detection:  # Feature flag
    from backend.segmentation.outlier_detection import OutlierDetector

    detector = OutlierDetector()
    outlier_analysis = detector.detect_outliers(profile.fuzzy_memberships)

    # Add to profile (non-breaking - optional field)
    profile.outlier_analysis = outlier_analysis
```

### 3.2 Dynamic K-Range (Enhancement to Existing)

**File**: `backend/segmentation/ecommerce_clustering_engine.py` (modify)

```python
# BEFORE (current):
def __init__(self, min_k: int = 2, max_k: int = 6, ...):
    self.min_k = min_k
    self.max_k = max_k

# AFTER (enhanced, backwards compatible):
def __init__(
    self,
    min_k: int = 2,
    max_k: int = 6,
    dynamic_k_range: bool = False,  # NEW FEATURE FLAG
    ...
):
    self.min_k = min_k
    self.max_k_base = max_k
    self.dynamic_k_range = dynamic_k_range

def _find_optimal_k(self, X: np.ndarray, axis_name: str) -> Tuple[int, float]:
    """Find optimal k with optional dynamic range"""

    # Determine max_k
    if self.dynamic_k_range:
        # Dynamic: Scale with population size
        n_customers = len(X)
        max_k = min(
            int(np.sqrt(n_customers) / 2),  # Rule of thumb
            20,  # Hard cap
            n_customers - 1  # Can't exceed population
        )
        max_k = max(max_k, self.min_k + 1)  # Ensure range exists
        logger.info(f"{axis_name}: Dynamic k-range [2, {max_k}] for n={n_customers}")
    else:
        # Static: Use configured max_k (original behavior)
        max_k = self.max_k_base

    # Rest of method unchanged...
    best_k = 2
    best_silhouette = -1

    for k in range(self.min_k, min(max_k + 1, len(X))):
        # ... existing logic
```

### 3.3 Alternative Clustering Algorithms (Experimental, Opt-In)

**File**: `backend/segmentation/advanced_clustering.py` (NEW)

```python
"""
Advanced Clustering Algorithms (Experimental)

Alternatives to K-Means for specific use cases.
Feature-flagged - does not replace K-Means by default.
"""

from sklearn.cluster import DBSCAN, HDBSCAN
from sklearn.mixture import GaussianMixture


class AdvancedClusteringEngine:
    """
    Experimental clustering methods.

    Methods:
        - HDBSCAN: For variable-density clusters
        - GMM: For elongated/elliptical clusters
        - DBSCAN: For outlier detection
    """

    def cluster_with_hdbscan(self, X: np.ndarray, min_cluster_size: int = 100):
        """
        HDBSCAN: Hierarchical DBSCAN

        Pros:
            - Finds variable-density clusters
            - No need to specify k
            - Identifies outliers/noise

        Cons:
            - Slower than K-Means
            - Less interpretable
            - Non-deterministic
        """
        clusterer = HDBSCAN(min_cluster_size=min_cluster_size)
        labels = clusterer.fit_predict(X)

        # -1 = noise/outliers
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        return labels, n_clusters

    def cluster_with_gmm(self, X: np.ndarray, k: int):
        """
        Gaussian Mixture Model

        Pros:
            - Handles elongated clusters
            - Soft clustering (probabilistic)
            - Covariance modeling

        Cons:
            - Slower than K-Means
            - Can overfit with small data
        """
        gmm = GaussianMixture(n_components=k, random_state=42)
        labels = gmm.fit_predict(X)
        probabilities = gmm.predict_proba(X)  # Fuzzy memberships!

        return labels, probabilities
```

**Usage** (opt-in via config):

```python
# In config or environment
CLUSTERING_ALGORITHM = os.getenv("CLUSTERING_ALGORITHM", "kmeans")  # "kmeans" | "hdbscan" | "gmm"

# In clustering engine
if self.algorithm == "hdbscan":
    from backend.segmentation.advanced_clustering import AdvancedClusteringEngine
    advanced = AdvancedClusteringEngine()
    labels, n_clusters = advanced.cluster_with_hdbscan(X_scaled)
else:
    # Original K-Means (default)
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
```

---

## 🧪 Phase 4: Testing & Validation
**Timeline**: Ongoing
**Risk**: Critical (ensures no regressions)

### 4.1 Unit Tests (New)

**File**: `backend/tests/test_snapshot_service.py`

```python
import pytest
from backend.services.snapshot_service import CustomerSnapshotService


@pytest.mark.asyncio
async def test_create_snapshot():
    """Test snapshot creation"""
    # Test implementation...
    pass


@pytest.mark.asyncio
async def test_prune_old_snapshots():
    """Test snapshot pruning logic"""
    # Test implementation...
    pass
```

**File**: `backend/tests/test_drift_analysis.py`

```python
import pytest
from backend.services.drift_analysis_service import DriftAnalysisService


@pytest.mark.asyncio
async def test_calculate_drift():
    """Test drift calculation accuracy"""
    # Test with known snapshots
    pass


@pytest.mark.asyncio
async def test_anomaly_detection():
    """Test anomaly detection sensitivity"""
    # Test with synthetic anomalies
    pass
```

### 4.2 Integration Tests (New)

**File**: `backend/tests/integration/test_temporal_features.py`

```python
@pytest.mark.asyncio
async def test_end_to_end_snapshot_workflow():
    """
    Test complete workflow:
        1. Create customer profile
        2. Create snapshot
        3. Update profile (simulate drift)
        4. Create new snapshot
        5. Analyze drift
        6. Verify results
    """
    # Test implementation...
    pass
```

### 4.3 Backwards Compatibility Tests (Critical)

**File**: `backend/tests/test_backwards_compatibility.py`

```python
@pytest.mark.asyncio
async def test_original_api_unchanged():
    """
    Ensure original customer profile API response unchanged.

    Critical: Must pass before deployment.
    """
    response = await client.get("/api/customers/12345")

    # Original fields must exist
    assert 'customer_id' in response.json()
    assert 'archetype' in response.json()
    assert 'dominant_segments' in response.json()
    assert 'fuzzy_memberships' in response.json()

    # New fields are optional (added alongside, not replacing)
    # If drift analysis enabled, these may appear:
    # - 'drift_analysis' (optional)
    # - 'outlier_analysis' (optional)


@pytest.mark.asyncio
async def test_clustering_produces_same_results():
    """
    Verify clustering algorithm produces identical results.

    Test with fixed seed and known dataset.
    """
    # Run original clustering
    original_segments = await original_clustering_engine.cluster_axis(...)

    # Run enhanced clustering (with new features disabled)
    enhanced_segments = await enhanced_clustering_engine.cluster_axis(...)

    # Results should be identical
    assert original_segments == enhanced_segments
```

---

## 🚀 Deployment Strategy

### Rollout Plan (Gradual, Reversible)

**Stage 1: Shadow Mode (Week 1-2)**
```python
# Deploy temporal snapshots
# Create snapshots in background
# NO user-facing changes
# Monitor: Storage usage, job performance
```

**Stage 2: Beta Testing (Week 3-4)**
```python
# Enable drift analysis for 10% of customers
# Add new API endpoints (opt-in)
# Monitor: API latency, drift calculation accuracy
# Collect feedback from team
```

**Stage 3: Full Rollout (Week 5-6)**
```python
# Enable for all customers
# Add drift analysis to frontend (optional display)
# Monitor: User engagement, performance impact
```

**Rollback Plan**:
```python
# Feature flags allow instant disable
ENABLE_TEMPORAL_SNAPSHOTS = os.getenv("ENABLE_TEMPORAL_SNAPSHOTS", "false")
ENABLE_DRIFT_ANALYSIS = os.getenv("ENABLE_DRIFT_ANALYSIS", "false")
ENABLE_OUTLIER_DETECTION = os.getenv("ENABLE_OUTLIER_DETECTION", "false")
ENABLE_ADVANCED_CLUSTERING = os.getenv("ENABLE_ADVANCED_CLUSTERING", "false")

# If issues arise, set env var to "false" and redeploy
# Original behavior restored immediately
```

---

## 📊 Success Metrics

### Phase 1 (Snapshots):
- ✅ Snapshots created for >95% of active customers daily
- ✅ Storage usage < 500 MB/month
- ✅ Snapshot job completes in < 30 minutes

### Phase 2 (Drift Analysis):
- ✅ Drift API latency < 500ms (p95)
- ✅ Anomaly detection accuracy > 80% (manual review)
- ✅ Zero regressions in existing API endpoints

### Phase 3 (Enhancements):
- ✅ Outlier detection identifies fraud/bots (manual validation)
- ✅ Dynamic k-range improves silhouette scores by 10%+
- ✅ Advanced clustering (HDBSCAN) tested on 3+ axes

---

## 🔒 Backwards Compatibility Checklist

Before any deployment:

- [ ] Original API endpoints return identical responses
- [ ] Original clustering algorithm produces same segments (with feature flags off)
- [ ] Database migrations are non-breaking (new tables only)
- [ ] All new features have feature flags (can be disabled)
- [ ] Performance benchmarks show < 10% regression
- [ ] Unit tests pass for both original and enhanced code
- [ ] Integration tests validate end-to-end workflows
- [ ] Rollback procedure tested and documented

---

## 📝 Documentation Updates

### For Developers:

- [ ] Update API documentation with new endpoints
- [ ] Add examples of drift analysis usage
- [ ] Document feature flags and configuration
- [ ] Create migration guide (optional features)

### For Users:

- [ ] Add "Behavioral Drift" section to customer profiles
- [ ] Create visualizations (trend charts, archetype journey)
- [ ] Explain drift scores and recommendations
- [ ] Provide use cases (churn prevention, lifecycle tracking)

---

## 🎯 Summary

This plan ensures:

1. ✅ **Original algorithm preserved** - All enhancements are additive, never replacing
2. ✅ **Feature-flagged** - Can disable any new feature instantly
3. ✅ **Non-breaking** - Existing APIs unchanged, new endpoints added alongside
4. ✅ **Reversible** - Rollback to original behavior with env var change
5. ✅ **Tested** - Comprehensive test suite ensures no regressions
6. ✅ **Gradual rollout** - Shadow mode → Beta → Full production
7. ✅ **Monitored** - Success metrics tracked at each phase

**Key Files** (all new, no modifications to core):
- `platform.customer_profile_snapshots` (new table)
- `backend/services/snapshot_service.py` (new)
- `backend/services/drift_analysis_service.py` (new)
- `backend/segmentation/outlier_detection.py` (new)
- `backend/segmentation/advanced_clustering.py` (new)
- `backend/jobs/create_snapshots_job.py` (new)
- `backend/api/routers/customers.py` (new endpoints added)

**Modified Files** (minimal, feature-flagged):
- `backend/segmentation/ecommerce_clustering_engine.py` (optional enhancements)
- `railway.toml` (add snapshot cron job)

The original clustering algorithm remains untouched and continues to work exactly as before. All enhancements are opt-in and reversible.
