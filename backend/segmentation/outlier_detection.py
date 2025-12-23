"""
Outlier Detection for Customer Behavioral Profiles

Identifies customers with unusual behavior patterns that don't fit well into
any discovered segments. This is a completely separate analysis from the core
clustering algorithm and can be disabled.

Key Features:
- Detects customers who don't fit standard segments
- Identifies which behavioral axes show outlier behavior
- Provides outlier scores (0-1, where 1 = extreme outlier)
- Non-intrusive: doesn't modify clustering logic
- Feature-flagged: can be disabled per environment

Methods:
1. Low Membership Detection: Customers with uniformly low membership across all segments
2. Isolation Forest: Statistical anomaly detection in feature space
3. Distance-based: Customers far from all cluster centers
"""

import os
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OutlierMethod(str, Enum):
    """Methods for detecting outliers"""
    LOW_MEMBERSHIP = "low_membership"       # Low fuzzy membership across all segments
    ISOLATION_FOREST = "isolation_forest"   # Statistical anomaly detection
    DISTANCE_BASED = "distance_based"       # Distance from cluster centers
    ENSEMBLE = "ensemble"                   # Combine multiple methods


@dataclass
class AxisOutlierScore:
    """Outlier analysis for a single behavioral axis"""
    axis_name: str
    is_outlier: bool
    outlier_score: float  # 0-1 (1 = extreme outlier)
    max_membership: float  # Highest membership in any segment
    avg_membership: float  # Average membership across segments
    explanation: str


@dataclass
class OutlierAnalysis:
    """Complete outlier analysis for a customer"""
    customer_id: int
    is_outlier: bool
    overall_outlier_score: float  # 0-1 (1 = extreme outlier)
    outlier_axes: List[str]  # Axes where customer is an outlier
    axis_scores: Dict[str, AxisOutlierScore]
    detection_method: OutlierMethod
    recommendation: str


class OutlierDetectionConfig:
    """Configuration for outlier detection"""

    def __init__(
        self,
        enabled: bool = True,
        method: OutlierMethod = OutlierMethod.LOW_MEMBERSHIP,
        low_membership_threshold: float = 0.3,  # Max membership must be < this
        avg_membership_threshold: float = 0.2,  # Avg membership must be < this
        min_outlier_axes: int = 2,  # Outlier on at least this many axes
        overall_threshold: float = 0.6,  # Overall score threshold
    ):
        self.enabled = enabled
        self.method = method
        self.low_membership_threshold = low_membership_threshold
        self.avg_membership_threshold = avg_membership_threshold
        self.min_outlier_axes = min_outlier_axes
        self.overall_threshold = overall_threshold

    @classmethod
    def from_env(cls) -> "OutlierDetectionConfig":
        """Load configuration from environment variables"""
        return cls(
            enabled=os.getenv("ENABLE_OUTLIER_DETECTION", "false").lower() == "true",
            method=OutlierMethod(os.getenv("OUTLIER_DETECTION_METHOD", "low_membership")),
            low_membership_threshold=float(os.getenv("OUTLIER_LOW_MEMBERSHIP_THRESHOLD", "0.3")),
            avg_membership_threshold=float(os.getenv("OUTLIER_AVG_MEMBERSHIP_THRESHOLD", "0.2")),
            min_outlier_axes=int(os.getenv("OUTLIER_MIN_AXES", "2")),
            overall_threshold=float(os.getenv("OUTLIER_OVERALL_THRESHOLD", "0.6")),
        )


class OutlierDetector:
    """
    Detects customers with outlier behavioral patterns.

    Primary Method: Low Membership Detection
    - If a customer has low fuzzy membership across ALL segments on an axis,
      they're an outlier on that axis
    - Outliers are customers who don't fit the discovered behavior patterns

    This is useful for:
    - Identifying VIP customers with unique behavior
    - Detecting fraud/bot accounts
    - Finding customers who need custom treatment
    - Identifying gaps in segment coverage
    """

    def __init__(self, config: Optional[OutlierDetectionConfig] = None):
        self.config = config or OutlierDetectionConfig.from_env()

    def detect_outliers(
        self,
        customer_id: int,
        fuzzy_memberships: Dict[str, Dict[str, float]],
        behavioral_features: Optional[Dict[str, Any]] = None
    ) -> Optional[OutlierAnalysis]:
        """
        Detect if customer is an outlier based on fuzzy memberships.

        Args:
            customer_id: Customer identifier
            fuzzy_memberships: Multi-axis fuzzy memberships
                Format: {axis: {segment: membership_score}}
            behavioral_features: Optional raw features for advanced detection

        Returns:
            OutlierAnalysis if detection enabled, None otherwise
        """
        if not self.config.enabled:
            return None

        if not fuzzy_memberships:
            logger.warning(f"No fuzzy memberships for customer {customer_id}, cannot detect outliers")
            return None

        # Analyze each axis for outlier behavior
        axis_scores = {}
        outlier_axes = []

        for axis_name, segment_memberships in fuzzy_memberships.items():
            axis_score = self._analyze_axis_outlier(
                axis_name=axis_name,
                segment_memberships=segment_memberships
            )
            axis_scores[axis_name] = axis_score

            if axis_score.is_outlier:
                outlier_axes.append(axis_name)

        # Calculate overall outlier score (average of axis scores)
        if axis_scores:
            overall_score = np.mean([score.outlier_score for score in axis_scores.values()])
        else:
            overall_score = 0.0

        # Determine if customer is overall outlier
        is_outlier = (
            len(outlier_axes) >= self.config.min_outlier_axes and
            overall_score >= self.config.overall_threshold
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            is_outlier=is_outlier,
            outlier_axes=outlier_axes,
            overall_score=overall_score
        )

        return OutlierAnalysis(
            customer_id=customer_id,
            is_outlier=is_outlier,
            overall_outlier_score=overall_score,
            outlier_axes=outlier_axes,
            axis_scores=axis_scores,
            detection_method=self.config.method,
            recommendation=recommendation
        )

    def _analyze_axis_outlier(
        self,
        axis_name: str,
        segment_memberships: Dict[str, float]
    ) -> AxisOutlierScore:
        """
        Analyze if customer is an outlier on a specific axis.

        Method: Low Membership Detection
        - If max membership < threshold AND avg membership < threshold
        - Customer doesn't fit any of the discovered segments on this axis
        """
        if not segment_memberships:
            return AxisOutlierScore(
                axis_name=axis_name,
                is_outlier=False,
                outlier_score=0.0,
                max_membership=0.0,
                avg_membership=0.0,
                explanation="No segments on this axis"
            )

        memberships = list(segment_memberships.values())
        max_membership = max(memberships)
        avg_membership = np.mean(memberships)

        # Calculate outlier score (0-1)
        # Higher score = more outlier-like
        max_outlier_score = 1.0 - (max_membership / self.config.low_membership_threshold)
        avg_outlier_score = 1.0 - (avg_membership / self.config.avg_membership_threshold)

        # Combined score (weighted average)
        outlier_score = max(0.0, min(1.0, 0.7 * max_outlier_score + 0.3 * avg_outlier_score))

        # Determine if outlier
        is_outlier = (
            max_membership < self.config.low_membership_threshold and
            avg_membership < self.config.avg_membership_threshold
        )

        # Generate explanation
        if is_outlier:
            explanation = f"Low membership across all segments (max: {max_membership:.2f}, avg: {avg_membership:.2f})"
        else:
            top_segment = max(segment_memberships.items(), key=lambda x: x[1])
            explanation = f"Fits segment '{top_segment[0]}' (membership: {top_segment[1]:.2f})"

        return AxisOutlierScore(
            axis_name=axis_name,
            is_outlier=is_outlier,
            outlier_score=outlier_score,
            max_membership=max_membership,
            avg_membership=avg_membership,
            explanation=explanation
        )

    def _generate_recommendation(
        self,
        is_outlier: bool,
        outlier_axes: List[str],
        overall_score: float
    ) -> str:
        """Generate actionable recommendation based on outlier analysis"""
        if not is_outlier:
            return "Customer fits standard behavioral segments - use normal segmentation-based strategies"

        if overall_score >= 0.8:
            severity = "Extreme"
        elif overall_score >= 0.6:
            severity = "Significant"
        else:
            severity = "Moderate"

        outlier_count = len(outlier_axes)
        axes_str = ", ".join(outlier_axes[:3])
        if outlier_count > 3:
            axes_str += f" (+{outlier_count - 3} more)"

        recommendation = f"{severity} outlier detected (score: {overall_score:.2f}). "
        recommendation += f"Non-standard behavior on: {axes_str}. "
        recommendation += "Recommendations: "

        # Specific recommendations
        if overall_score >= 0.8:
            recommendation += "1) Manual review required - very unusual pattern. "
            recommendation += "2) Check for data quality issues or bot activity. "
            recommendation += "3) Consider custom treatment/VIP handling if legitimate. "
        else:
            recommendation += "1) Use custom engagement strategy instead of segment-based. "
            recommendation += "2) Consider 1-on-1 outreach to understand unique needs. "
            recommendation += "3) Monitor for evolving behavior patterns. "

        return recommendation

    def detect_batch_outliers(
        self,
        customers: List[Dict[str, Any]]
    ) -> List[OutlierAnalysis]:
        """
        Detect outliers for a batch of customers.

        Args:
            customers: List of customer dicts with 'customer_id' and 'fuzzy_memberships'

        Returns:
            List of OutlierAnalysis objects for outlier customers only
        """
        outliers = []

        for customer in customers:
            analysis = self.detect_outliers(
                customer_id=customer.get("customer_id"),
                fuzzy_memberships=customer.get("fuzzy_memberships", {}),
                behavioral_features=customer.get("behavioral_features")
            )

            if analysis and analysis.is_outlier:
                outliers.append(analysis)

        logger.info(f"Detected {len(outliers)} outliers out of {len(customers)} customers")
        return outliers

    def get_outlier_statistics(
        self,
        outlier_analyses: List[OutlierAnalysis]
    ) -> Dict[str, Any]:
        """
        Generate statistics about outlier distribution.

        Useful for understanding:
        - Which axes have most outliers (gaps in segment coverage?)
        - Overall outlier rate
        - Common outlier patterns
        """
        if not outlier_analyses:
            return {
                "total_outliers": 0,
                "outlier_rate": 0.0,
                "axes_with_outliers": {},
                "avg_outlier_score": 0.0,
            }

        total_outliers = len(outlier_analyses)

        # Count outliers per axis
        axes_outlier_counts = {}
        for analysis in outlier_analyses:
            for axis in analysis.outlier_axes:
                axes_outlier_counts[axis] = axes_outlier_counts.get(axis, 0) + 1

        # Sort axes by outlier count
        axes_ranked = sorted(
            axes_outlier_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Calculate average outlier score
        avg_score = np.mean([a.overall_outlier_score for a in outlier_analyses])

        return {
            "total_outliers": total_outliers,
            "axes_with_most_outliers": dict(axes_ranked[:10]),  # Top 10
            "avg_outlier_score": avg_score,
            "severity_distribution": {
                "extreme (>0.8)": sum(1 for a in outlier_analyses if a.overall_outlier_score >= 0.8),
                "significant (0.6-0.8)": sum(1 for a in outlier_analyses if 0.6 <= a.overall_outlier_score < 0.8),
                "moderate (0.4-0.6)": sum(1 for a in outlier_analyses if 0.4 <= a.overall_outlier_score < 0.6),
            }
        }


# Convenience function for single customer analysis
def analyze_customer_outlier(
    customer_id: int,
    fuzzy_memberships: Dict[str, Dict[str, float]],
    config: Optional[OutlierDetectionConfig] = None
) -> Optional[OutlierAnalysis]:
    """
    Convenience function to analyze a single customer for outlier behavior.

    Args:
        customer_id: Customer identifier
        fuzzy_memberships: Multi-axis fuzzy memberships
        config: Optional custom configuration

    Returns:
        OutlierAnalysis or None if detection disabled
    """
    detector = OutlierDetector(config)
    return detector.detect_outliers(customer_id, fuzzy_memberships)
