"""
Behavioral Drift Analysis Service

Analyzes how customer behavioral profiles change over time using temporal snapshots.
Calculates drift metrics, detects anomalies, and identifies trend patterns.

Key Metrics:
- Euclidean distance in fuzzy membership space
- Segment transition tracking
- Drift velocity (rate of change)
- Direction of drift (which axes changing most)
- Anomaly detection (sudden large changes)
"""

import numpy as np
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from .snapshot_service import CustomerSnapshot, SnapshotType

logger = logging.getLogger(__name__)


class DriftSeverity(str, Enum):
    """Severity levels for behavioral drift"""
    STABLE = "stable"           # < 0.1 drift score
    MINOR = "minor"             # 0.1 - 0.3
    MODERATE = "moderate"       # 0.3 - 0.5
    SIGNIFICANT = "significant" # 0.5 - 0.7
    MAJOR = "major"             # > 0.7


@dataclass
class AxisDrift:
    """Drift metrics for a single behavioral axis"""
    axis_name: str
    drift_score: float          # 0.0 (no drift) to 1.0 (complete change)
    old_dominant_segment: str
    new_dominant_segment: str
    segment_changed: bool
    old_membership: Dict[str, float]  # {segment: membership_score}
    new_membership: Dict[str, float]


@dataclass
class DriftAnalysis:
    """Complete drift analysis between two snapshots"""
    customer_id: int
    start_date: date
    end_date: date
    days_elapsed: int

    # Overall drift metrics
    overall_drift_score: float      # 0.0 to 1.0
    drift_severity: DriftSeverity
    drift_velocity: float           # Drift per day

    # Per-axis drift
    axis_drifts: Dict[str, AxisDrift]

    # Segment transitions
    segments_changed: List[str]     # Axes where dominant segment changed
    transition_count: int

    # ML prediction drift
    churn_risk_delta: Optional[float]  # Change in churn risk
    ltv_delta: Optional[float]         # Change in predicted LTV

    # Flags
    is_anomaly: bool                # Sudden large drift
    is_improving: bool              # Positive trend (lower churn, higher LTV)
    is_declining: bool              # Negative trend


class DriftAnalysisService:
    """Service for analyzing behavioral drift between snapshots"""

    def __init__(self, drift_threshold: float = 0.1, anomaly_threshold: float = 0.5):
        """
        Initialize drift analysis service.

        Args:
            drift_threshold: Minimum drift score to consider meaningful (default: 0.1)
            anomaly_threshold: Drift score threshold for anomaly detection (default: 0.5)
        """
        self.drift_threshold = drift_threshold
        self.anomaly_threshold = anomaly_threshold

    def analyze_drift(
        self,
        old_snapshot: CustomerSnapshot,
        new_snapshot: CustomerSnapshot
    ) -> DriftAnalysis:
        """
        Analyze behavioral drift between two snapshots.

        Args:
            old_snapshot: Earlier snapshot
            new_snapshot: Later snapshot

        Returns:
            DriftAnalysis object with drift metrics
        """
        # Validate inputs
        if old_snapshot.customer_id != new_snapshot.customer_id:
            raise ValueError("Snapshots must be for the same customer")

        if old_snapshot.snapshot_date >= new_snapshot.snapshot_date:
            raise ValueError("old_snapshot must be earlier than new_snapshot")

        # Calculate time delta
        days_elapsed = (new_snapshot.snapshot_date - old_snapshot.snapshot_date).days

        # Calculate per-axis drift
        axis_drifts = self._calculate_axis_drifts(
            old_snapshot.fuzzy_memberships,
            new_snapshot.fuzzy_memberships
        )

        # Calculate overall drift score (average across axes)
        overall_drift = np.mean([drift.drift_score for drift in axis_drifts.values()]) if axis_drifts else 0.0

        # Calculate drift velocity (drift per day)
        drift_velocity = overall_drift / days_elapsed if days_elapsed > 0 else 0.0

        # Determine severity
        drift_severity = self._determine_severity(overall_drift)

        # Detect segment transitions
        segments_changed = [
            axis for axis, drift in axis_drifts.items()
            if drift.segment_changed
        ]

        # Calculate ML prediction drift
        churn_risk_delta = None
        ltv_delta = None

        if old_snapshot.churn_risk_score is not None and new_snapshot.churn_risk_score is not None:
            churn_risk_delta = new_snapshot.churn_risk_score - old_snapshot.churn_risk_score

        if old_snapshot.predicted_ltv is not None and new_snapshot.predicted_ltv is not None:
            ltv_delta = new_snapshot.predicted_ltv - old_snapshot.predicted_ltv

        # Determine trends
        is_improving = self._is_improving_trend(churn_risk_delta, ltv_delta)
        is_declining = self._is_declining_trend(churn_risk_delta, ltv_delta)

        # Detect anomalies (sudden large drift)
        is_anomaly = overall_drift >= self.anomaly_threshold

        return DriftAnalysis(
            customer_id=new_snapshot.customer_id,
            start_date=old_snapshot.snapshot_date,
            end_date=new_snapshot.snapshot_date,
            days_elapsed=days_elapsed,
            overall_drift_score=overall_drift,
            drift_severity=drift_severity,
            drift_velocity=drift_velocity,
            axis_drifts=axis_drifts,
            segments_changed=segments_changed,
            transition_count=len(segments_changed),
            churn_risk_delta=churn_risk_delta,
            ltv_delta=ltv_delta,
            is_anomaly=is_anomaly,
            is_improving=is_improving,
            is_declining=is_declining,
        )

    def _calculate_axis_drifts(
        self,
        old_memberships: Dict[str, Dict[str, float]],
        new_memberships: Dict[str, Dict[str, float]]
    ) -> Dict[str, AxisDrift]:
        """
        Calculate drift for each behavioral axis.

        Uses Euclidean distance in fuzzy membership space:
        drift = sqrt(Σ (membership_new[seg] - membership_old[seg])^2) / sqrt(2)

        Normalized to [0, 1] where:
        - 0.0 = no drift (identical memberships)
        - 1.0 = maximum drift (complete opposite membership)
        """
        axis_drifts = {}

        # Get all axes (union of old and new)
        all_axes = set(old_memberships.keys()) | set(new_memberships.keys())

        for axis in all_axes:
            old_axis_membership = old_memberships.get(axis, {})
            new_axis_membership = new_memberships.get(axis, {})

            # Get all segments for this axis
            all_segments = set(old_axis_membership.keys()) | set(new_axis_membership.keys())

            # Calculate Euclidean distance
            distance_squared = 0.0
            for segment in all_segments:
                old_score = old_axis_membership.get(segment, 0.0)
                new_score = new_axis_membership.get(segment, 0.0)
                distance_squared += (new_score - old_score) ** 2

            # Normalize to [0, 1]
            # Max possible distance is sqrt(2) when all membership shifts from one segment to another
            drift_score = min(np.sqrt(distance_squared) / np.sqrt(2), 1.0)

            # Find dominant segments (highest membership)
            old_dominant = max(old_axis_membership.items(), key=lambda x: x[1])[0] if old_axis_membership else "unknown"
            new_dominant = max(new_axis_membership.items(), key=lambda x: x[1])[0] if new_axis_membership else "unknown"

            segment_changed = old_dominant != new_dominant

            axis_drifts[axis] = AxisDrift(
                axis_name=axis,
                drift_score=drift_score,
                old_dominant_segment=old_dominant,
                new_dominant_segment=new_dominant,
                segment_changed=segment_changed,
                old_membership=old_axis_membership,
                new_membership=new_axis_membership,
            )

        return axis_drifts

    def _determine_severity(self, drift_score: float) -> DriftSeverity:
        """Map drift score to severity level"""
        if drift_score < 0.1:
            return DriftSeverity.STABLE
        elif drift_score < 0.3:
            return DriftSeverity.MINOR
        elif drift_score < 0.5:
            return DriftSeverity.MODERATE
        elif drift_score < 0.7:
            return DriftSeverity.SIGNIFICANT
        else:
            return DriftSeverity.MAJOR

    def _is_improving_trend(
        self,
        churn_delta: Optional[float],
        ltv_delta: Optional[float]
    ) -> bool:
        """
        Determine if customer is improving (positive trend).

        Improving = decreasing churn OR increasing LTV
        """
        improving = False

        if churn_delta is not None and churn_delta < -0.05:  # Churn decreased by >5%
            improving = True

        if ltv_delta is not None and ltv_delta > 0:  # LTV increased
            improving = True

        return improving

    def _is_declining_trend(
        self,
        churn_delta: Optional[float],
        ltv_delta: Optional[float]
    ) -> bool:
        """
        Determine if customer is declining (negative trend).

        Declining = increasing churn OR decreasing LTV
        """
        declining = False

        if churn_delta is not None and churn_delta > 0.05:  # Churn increased by >5%
            declining = True

        if ltv_delta is not None and ltv_delta < 0:  # LTV decreased
            declining = True

        return declining

    def analyze_drift_timeline(
        self,
        snapshots: List[CustomerSnapshot]
    ) -> List[DriftAnalysis]:
        """
        Analyze drift across a timeline of snapshots.

        Args:
            snapshots: List of snapshots ordered by date (oldest to newest)

        Returns:
            List of DriftAnalysis objects (one per consecutive snapshot pair)
        """
        if len(snapshots) < 2:
            logger.warning("Need at least 2 snapshots for drift analysis")
            return []

        # Sort snapshots by date (oldest first)
        sorted_snapshots = sorted(snapshots, key=lambda s: s.snapshot_date)

        drift_analyses = []

        # Compare each consecutive pair
        for i in range(len(sorted_snapshots) - 1):
            old_snapshot = sorted_snapshots[i]
            new_snapshot = sorted_snapshots[i + 1]

            analysis = self.analyze_drift(old_snapshot, new_snapshot)
            drift_analyses.append(analysis)

        return drift_analyses

    def get_drift_summary(
        self,
        drift_analyses: List[DriftAnalysis]
    ) -> Dict[str, any]:
        """
        Generate summary statistics across multiple drift analyses.

        Args:
            drift_analyses: List of DriftAnalysis objects

        Returns:
            Dictionary with summary metrics
        """
        if not drift_analyses:
            return {
                "total_periods": 0,
                "average_drift_score": 0.0,
                "max_drift_score": 0.0,
                "anomaly_count": 0,
                "total_segment_transitions": 0,
                "improving_periods": 0,
                "declining_periods": 0,
            }

        drift_scores = [a.overall_drift_score for a in drift_analyses]
        segment_transitions = sum(a.transition_count for a in drift_analyses)
        anomaly_count = sum(1 for a in drift_analyses if a.is_anomaly)
        improving_count = sum(1 for a in drift_analyses if a.is_improving)
        declining_count = sum(1 for a in drift_analyses if a.is_declining)

        # Find most volatile axes (highest average drift)
        axis_drift_totals = {}
        axis_counts = {}

        for analysis in drift_analyses:
            for axis_name, axis_drift in analysis.axis_drifts.items():
                if axis_name not in axis_drift_totals:
                    axis_drift_totals[axis_name] = 0.0
                    axis_counts[axis_name] = 0

                axis_drift_totals[axis_name] += axis_drift.drift_score
                axis_counts[axis_name] += 1

        most_volatile_axes = sorted(
            [(axis, axis_drift_totals[axis] / axis_counts[axis])
             for axis in axis_drift_totals],
            key=lambda x: x[1],
            reverse=True
        )

        return {
            "total_periods": len(drift_analyses),
            "average_drift_score": np.mean(drift_scores),
            "max_drift_score": np.max(drift_scores),
            "min_drift_score": np.min(drift_scores),
            "drift_volatility": np.std(drift_scores),  # Standard deviation
            "anomaly_count": anomaly_count,
            "total_segment_transitions": segment_transitions,
            "improving_periods": improving_count,
            "declining_periods": declining_count,
            "most_volatile_axes": most_volatile_axes[:5],  # Top 5
            "overall_trend": "improving" if improving_count > declining_count else "declining" if declining_count > improving_count else "stable",
        }

    def detect_drift_patterns(
        self,
        drift_analyses: List[DriftAnalysis]
    ) -> Dict[str, any]:
        """
        Detect behavioral drift patterns.

        Patterns:
        - Steady drift: Consistent change in one direction
        - Oscillating: Drifting back and forth
        - Accelerating: Drift velocity increasing over time
        - Stabilizing: Drift velocity decreasing over time
        """
        if len(drift_analyses) < 3:
            return {"pattern": "insufficient_data"}

        # Calculate drift velocity trend
        velocities = [a.drift_velocity for a in drift_analyses]

        # Linear regression on velocities to detect acceleration/deceleration
        x = np.arange(len(velocities))
        slope = np.polyfit(x, velocities, 1)[0] if len(x) > 1 else 0.0

        # Detect oscillation by checking direction changes
        direction_changes = 0
        for i in range(1, len(drift_analyses)):
            prev_drift = drift_analyses[i-1].overall_drift_score
            curr_drift = drift_analyses[i].overall_drift_score
            if (prev_drift > 0 and curr_drift < 0) or (prev_drift < 0 and curr_drift > 0):
                direction_changes += 1

        oscillation_ratio = direction_changes / (len(drift_analyses) - 1)

        # Determine pattern
        pattern = "stable"
        if oscillation_ratio > 0.5:
            pattern = "oscillating"
        elif slope > 0.01:
            pattern = "accelerating"
        elif slope < -0.01:
            pattern = "stabilizing"
        elif np.mean(velocities) > 0.02:
            pattern = "steady_drift"

        return {
            "pattern": pattern,
            "velocity_slope": slope,
            "oscillation_ratio": oscillation_ratio,
            "average_velocity": np.mean(velocities),
            "description": self._get_pattern_description(pattern),
        }

    def _get_pattern_description(self, pattern: str) -> str:
        """Get human-readable description of drift pattern"""
        descriptions = {
            "stable": "Customer behavior is stable with minimal drift",
            "steady_drift": "Customer behavior is changing steadily over time",
            "oscillating": "Customer behavior is oscillating between states",
            "accelerating": "Behavioral drift is accelerating (increasing volatility)",
            "stabilizing": "Behavioral drift is stabilizing (decreasing volatility)",
            "insufficient_data": "Not enough snapshots to detect patterns (need 3+)",
        }
        return descriptions.get(pattern, "Unknown pattern")
