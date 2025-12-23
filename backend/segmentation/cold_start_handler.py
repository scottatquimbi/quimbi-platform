"""
Cold Start Handler for New Customers

Handles customers with insufficient data for reliable behavioral segmentation.
Provides intelligent fallback strategies until enough data is collected.

Key Features:
- Detects cold start conditions (new customers, limited orders)
- Provides confidence scores for segmentation
- Uses intelligent defaults based on limited data
- Progressive profiling as more data arrives
- Non-intrusive: doesn't modify core clustering logic

Strategies:
1. Data Sufficiency Check: Determine if enough data for clustering
2. Fallback Segmentation: Use simple rules until clustering is reliable
3. Confidence Scoring: Indicate reliability of behavioral profile
4. Progressive Updates: Re-profile as new data arrives
"""

import os
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CustomerLifecycleStage(str, Enum):
    """Lifecycle stage based on data availability"""
    COLD_START = "cold_start"           # 0-1 orders
    WARMING_UP = "warming_up"           # 2-4 orders
    ESTABLISHED = "established"         # 5-9 orders
    MATURE = "mature"                   # 10+ orders


class DataSufficiency(str, Enum):
    """Data sufficiency levels for segmentation"""
    INSUFFICIENT = "insufficient"       # Too little data for clustering
    MINIMAL = "minimal"                 # Bare minimum for clustering
    ADEQUATE = "adequate"               # Good data quality
    RICH = "rich"                       # Abundant data


@dataclass
class ColdStartProfile:
    """Customer profile during cold start period"""
    customer_id: int
    lifecycle_stage: CustomerLifecycleStage
    data_sufficiency: DataSufficiency
    confidence_score: float  # 0-1 (reliability of segmentation)

    # Available data
    total_orders: int
    total_value: float
    days_since_first_order: int
    days_since_last_order: int

    # Fallback segments (simple rule-based)
    fallback_segments: Dict[str, str]  # {axis: segment_name}
    fallback_confidence: Dict[str, float]  # {axis: confidence}

    # Recommendations
    data_needed: List[str]  # What data points would improve profiling
    estimated_days_until_mature: Optional[int]
    recommendation: str


class ColdStartConfig:
    """Configuration for cold start handling"""

    def __init__(
        self,
        enabled: bool = True,
        min_orders_for_clustering: int = 3,
        min_orders_for_adequate: int = 5,
        min_orders_for_rich: int = 10,
        min_tenure_days: int = 7,
        confidence_decay_rate: float = 0.1,  # Confidence decreases with less data
    ):
        self.enabled = enabled
        self.min_orders_for_clustering = min_orders_for_clustering
        self.min_orders_for_adequate = min_orders_for_adequate
        self.min_orders_for_rich = min_orders_for_rich
        self.min_tenure_days = min_tenure_days
        self.confidence_decay_rate = confidence_decay_rate

    @classmethod
    def from_env(cls) -> "ColdStartConfig":
        """Load configuration from environment variables"""
        return cls(
            enabled=os.getenv("ENABLE_COLD_START_HANDLING", "true").lower() == "true",
            min_orders_for_clustering=int(os.getenv("COLD_START_MIN_ORDERS", "3")),
            min_orders_for_adequate=int(os.getenv("COLD_START_ADEQUATE_ORDERS", "5")),
            min_orders_for_rich=int(os.getenv("COLD_START_RICH_ORDERS", "10")),
            min_tenure_days=int(os.getenv("COLD_START_MIN_TENURE_DAYS", "7")),
        )


class ColdStartHandler:
    """
    Handles customers with insufficient data for reliable segmentation.

    Primary Functions:
    1. Detect cold start conditions
    2. Provide confidence scores
    3. Generate fallback segments using simple rules
    4. Recommend data collection strategies
    """

    def __init__(self, config: Optional[ColdStartConfig] = None):
        self.config = config or ColdStartConfig.from_env()

    def analyze_customer(
        self,
        customer_id: int,
        total_orders: int,
        total_value: float,
        first_order_date: date,
        last_order_date: date,
        current_fuzzy_memberships: Optional[Dict[str, Dict[str, float]]] = None
    ) -> ColdStartProfile:
        """
        Analyze if customer is in cold start and provide fallback profile.

        Args:
            customer_id: Customer identifier
            total_orders: Number of orders placed
            total_value: Total lifetime value
            first_order_date: Date of first order
            last_order_date: Date of most recent order
            current_fuzzy_memberships: Current clustering results (if available)

        Returns:
            ColdStartProfile with analysis and recommendations
        """
        # Calculate temporal metrics
        days_since_first = (date.today() - first_order_date).days
        days_since_last = (date.today() - last_order_date).days

        # Determine lifecycle stage
        lifecycle_stage = self._determine_lifecycle_stage(total_orders)

        # Determine data sufficiency
        data_sufficiency = self._determine_data_sufficiency(
            total_orders, days_since_first
        )

        # Calculate confidence score
        confidence = self._calculate_confidence(
            total_orders, days_since_first, current_fuzzy_memberships
        )

        # Generate fallback segments using simple rules
        fallback_segments, fallback_confidence = self._generate_fallback_segments(
            total_orders, total_value, days_since_first, days_since_last
        )

        # Identify needed data
        data_needed = self._identify_needed_data(
            total_orders, days_since_first
        )

        # Estimate time to mature
        estimated_days = self._estimate_days_until_mature(
            total_orders, days_since_first
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            lifecycle_stage, data_sufficiency, confidence, data_needed
        )

        return ColdStartProfile(
            customer_id=customer_id,
            lifecycle_stage=lifecycle_stage,
            data_sufficiency=data_sufficiency,
            confidence_score=confidence,
            total_orders=total_orders,
            total_value=total_value,
            days_since_first_order=days_since_first,
            days_since_last_order=days_since_last,
            fallback_segments=fallback_segments,
            fallback_confidence=fallback_confidence,
            data_needed=data_needed,
            estimated_days_until_mature=estimated_days,
            recommendation=recommendation
        )

    def _determine_lifecycle_stage(self, total_orders: int) -> CustomerLifecycleStage:
        """Determine customer lifecycle stage based on order count"""
        if total_orders <= 1:
            return CustomerLifecycleStage.COLD_START
        elif total_orders <= 4:
            return CustomerLifecycleStage.WARMING_UP
        elif total_orders <= 9:
            return CustomerLifecycleStage.ESTABLISHED
        else:
            return CustomerLifecycleStage.MATURE

    def _determine_data_sufficiency(
        self, total_orders: int, tenure_days: int
    ) -> DataSufficiency:
        """Determine if data is sufficient for reliable clustering"""
        if total_orders < self.config.min_orders_for_clustering:
            return DataSufficiency.INSUFFICIENT

        if tenure_days < self.config.min_tenure_days:
            return DataSufficiency.INSUFFICIENT

        if total_orders < self.config.min_orders_for_adequate:
            return DataSufficiency.MINIMAL

        if total_orders >= self.config.min_orders_for_rich:
            return DataSufficiency.RICH

        return DataSufficiency.ADEQUATE

    def _calculate_confidence(
        self,
        total_orders: int,
        tenure_days: int,
        current_memberships: Optional[Dict[str, Dict[str, float]]]
    ) -> float:
        """
        Calculate confidence score for segmentation.

        Factors:
        - Order count (more orders = higher confidence)
        - Tenure (longer tenure = higher confidence)
        - Fuzzy membership quality (if available)
        """
        # Base confidence from order count
        order_confidence = min(1.0, total_orders / self.config.min_orders_for_rich)

        # Tenure confidence
        tenure_confidence = min(1.0, tenure_days / 90)  # 90 days = full confidence

        # Fuzzy membership confidence (if available)
        membership_confidence = 1.0
        if current_memberships:
            # Average of max memberships across axes
            max_memberships = []
            for axis_memberships in current_memberships.values():
                if axis_memberships:
                    max_memberships.append(max(axis_memberships.values()))

            if max_memberships:
                membership_confidence = np.mean(max_memberships)

        # Weighted average
        confidence = (
            0.4 * order_confidence +
            0.3 * tenure_confidence +
            0.3 * membership_confidence
        )

        return confidence

    def _generate_fallback_segments(
        self,
        total_orders: int,
        total_value: float,
        days_since_first: int,
        days_since_last: int
    ) -> Tuple[Dict[str, str], Dict[str, float]]:
        """
        Generate simple rule-based segments for cold start customers.

        These are basic segments until enough data for clustering.
        """
        fallback_segments = {}
        fallback_confidence = {}

        # Purchase Frequency (simple rule-based)
        if total_orders == 1:
            fallback_segments['purchase_frequency'] = "One-Time Buyer"
            fallback_confidence['purchase_frequency'] = 0.9  # High confidence
        elif total_orders <= 3:
            fallback_segments['purchase_frequency'] = "Occasional Shopper"
            fallback_confidence['purchase_frequency'] = 0.7
        elif total_orders <= 6:
            fallback_segments['purchase_frequency'] = "Regular Buyer"
            fallback_confidence['purchase_frequency'] = 0.6
        else:
            fallback_segments['purchase_frequency'] = "Frequent Shopper"
            fallback_confidence['purchase_frequency'] = 0.5

        # Purchase Value (simple thresholds)
        if total_value == 0:
            avg_order_value = 0
        else:
            avg_order_value = total_value / max(total_orders, 1)

        if avg_order_value < 30:
            fallback_segments['purchase_value'] = "Budget Conscious"
            fallback_confidence['purchase_value'] = 0.6
        elif avg_order_value < 75:
            fallback_segments['purchase_value'] = "Mid-Range"
            fallback_confidence['purchase_value'] = 0.6
        else:
            fallback_segments['purchase_value'] = "Premium Buyer"
            fallback_confidence['purchase_value'] = 0.7

        # Engagement Level (based on recency)
        if days_since_last <= 7:
            fallback_segments['engagement_level'] = "Highly Engaged"
            fallback_confidence['engagement_level'] = 0.8
        elif days_since_last <= 30:
            fallback_segments['engagement_level'] = "Active"
            fallback_confidence['engagement_level'] = 0.7
        elif days_since_last <= 90:
            fallback_segments['engagement_level'] = "Casual"
            fallback_confidence['engagement_level'] = 0.6
        else:
            fallback_segments['engagement_level'] = "Dormant"
            fallback_confidence['engagement_level'] = 0.7

        return fallback_segments, fallback_confidence

    def _identify_needed_data(
        self, total_orders: int, tenure_days: int
    ) -> List[str]:
        """Identify what additional data would improve profiling"""
        needed = []

        if total_orders < self.config.min_orders_for_clustering:
            needed.append(f"At least {self.config.min_orders_for_clustering - total_orders} more orders for basic clustering")

        if total_orders < self.config.min_orders_for_adequate:
            needed.append(f"{self.config.min_orders_for_adequate - total_orders} more orders for adequate profiling")

        if tenure_days < self.config.min_tenure_days:
            needed.append(f"{self.config.min_tenure_days - tenure_days} more days of tenure")

        if tenure_days < 90:
            needed.append("More time to observe behavioral patterns (90+ days ideal)")

        # Suggest specific behavioral data
        if total_orders < 5:
            needed.append("More orders to analyze category preferences")
            needed.append("Additional interactions to measure engagement")

        return needed

    def _estimate_days_until_mature(
        self, total_orders: int, tenure_days: int
    ) -> Optional[int]:
        """
        Estimate days until customer reaches mature stage.

        Assumes average order frequency continues.
        """
        if total_orders >= self.config.min_orders_for_rich:
            return 0  # Already mature

        if total_orders == 0 or tenure_days == 0:
            return None  # Cannot estimate

        # Calculate current order frequency (orders per day)
        order_frequency = total_orders / tenure_days

        if order_frequency == 0:
            return None

        # Orders needed to reach mature
        orders_needed = self.config.min_orders_for_rich - total_orders

        # Days needed at current frequency
        days_needed = int(orders_needed / order_frequency)

        return days_needed

    def _generate_recommendation(
        self,
        lifecycle_stage: CustomerLifecycleStage,
        data_sufficiency: DataSufficiency,
        confidence: float,
        data_needed: List[str]
    ) -> str:
        """Generate actionable recommendation"""
        if lifecycle_stage == CustomerLifecycleStage.COLD_START:
            rec = "🆕 NEW CUSTOMER: Use welcome campaign and first-purchase incentives. "
            rec += "Behavioral profiling not yet reliable - collect more data before targeting. "

        elif lifecycle_stage == CustomerLifecycleStage.WARMING_UP:
            rec = "🔥 WARMING UP: Customer showing initial engagement. "
            rec += "Focus on retention and second purchase encouragement. "
            rec += "Limited behavioral data - use broad targeting. "

        elif lifecycle_stage == CustomerLifecycleStage.ESTABLISHED:
            rec = "📊 ESTABLISHED: Sufficient data for basic profiling. "
            rec += f"Confidence: {confidence:.0%}. "
            rec += "Can use behavioral segments with moderate confidence. "

        else:  # MATURE
            rec = "✅ MATURE: Rich behavioral data available. "
            rec += f"Confidence: {confidence:.0%}. "
            rec += "Full segmentation-based targeting recommended. "

        if data_sufficiency == DataSufficiency.INSUFFICIENT:
            rec += "⚠️  INSUFFICIENT DATA for clustering - using rule-based fallback segments. "

        return rec

    def should_use_clustering(
        self, customer_profile: ColdStartProfile
    ) -> bool:
        """
        Determine if customer has enough data for clustering.

        Returns False if should use fallback segments instead.
        """
        return (
            customer_profile.data_sufficiency != DataSufficiency.INSUFFICIENT and
            customer_profile.confidence_score >= 0.3
        )

    def enrich_profile_with_cold_start_info(
        self,
        customer_profile: Dict[str, Any],
        cold_start_profile: ColdStartProfile
    ) -> Dict[str, Any]:
        """
        Enrich customer profile with cold start information.

        Adds metadata about data quality and confidence.
        Does NOT modify core segmentation - only adds context.
        """
        customer_profile['cold_start_info'] = {
            'lifecycle_stage': cold_start_profile.lifecycle_stage.value,
            'data_sufficiency': cold_start_profile.data_sufficiency.value,
            'confidence_score': cold_start_profile.confidence_score,
            'days_since_first_order': cold_start_profile.days_since_first_order,
            'estimated_days_until_mature': cold_start_profile.estimated_days_until_mature,
            'recommendation': cold_start_profile.recommendation,
        }

        # If using fallback segments, add them
        if not self.should_use_clustering(cold_start_profile):
            customer_profile['fallback_segments'] = cold_start_profile.fallback_segments
            customer_profile['fallback_confidence'] = cold_start_profile.fallback_confidence
            customer_profile['using_fallback'] = True
        else:
            customer_profile['using_fallback'] = False

        return customer_profile


# Convenience function
def analyze_cold_start(
    customer_id: int,
    total_orders: int,
    total_value: float,
    first_order_date: date,
    last_order_date: date
) -> ColdStartProfile:
    """
    Convenience function to analyze if customer is in cold start.

    Args:
        customer_id: Customer identifier
        total_orders: Number of orders
        total_value: Lifetime value
        first_order_date: Date of first order
        last_order_date: Date of last order

    Returns:
        ColdStartProfile with analysis
    """
    handler = ColdStartHandler()
    return handler.analyze_customer(
        customer_id, total_orders, total_value,
        first_order_date, last_order_date
    )
