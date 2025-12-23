"""
Clustering Quality Improvements

Fixes the "everyone vs outliers" problem by adding:
1. Robust outlier preprocessing (Winsorization)
2. Configurable segment balance validation
3. Adaptive k-range selection
4. Segment quality metrics

Author: Quimbi Platform
Date: 2025-12-14
"""

import numpy as np
import os
from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
import logging
from sklearn.preprocessing import RobustScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class ClusteringConfig:
    """Configuration for improved clustering"""

    # K-range selection
    min_k: int = 3  # Increased from 2 to avoid binary clustering
    max_k: int = 8  # Increased from 6 for more granularity

    # Segment balance constraints (configurable, not hardcoded!)
    max_dominant_segment_pct: float = 50.0  # Max % in largest segment (default: 50%)
    min_segment_size_pct: float = 3.0       # Min % per segment (default: 3%)

    # Quality thresholds
    min_silhouette: float = 0.35  # Slightly higher threshold

    # Outlier preprocessing
    enable_robust_scaling: bool = True
    winsorize_percentile: float = 99.0  # Cap extreme values at 99th percentile

    # Adaptive behavior
    max_rebalance_attempts: int = 3  # How many times to retry with higher k

    @classmethod
    def from_env(cls) -> 'ClusteringConfig':
        """Load configuration from environment variables"""
        return cls(
            min_k=int(os.getenv("CLUSTERING_MIN_K", "3")),
            max_k=int(os.getenv("CLUSTERING_MAX_K", "8")),
            max_dominant_segment_pct=float(os.getenv("CLUSTERING_MAX_DOMINANT_PCT", "50.0")),
            min_segment_size_pct=float(os.getenv("CLUSTERING_MIN_SEGMENT_PCT", "3.0")),
            min_silhouette=float(os.getenv("CLUSTERING_MIN_SILHOUETTE", "0.35")),
            enable_robust_scaling=os.getenv("CLUSTERING_ROBUST_SCALING", "true").lower() == "true",
            winsorize_percentile=float(os.getenv("CLUSTERING_WINSORIZE_PCT", "99.0")),
            max_rebalance_attempts=int(os.getenv("CLUSTERING_MAX_REBALANCE", "3")),
        )


@dataclass
class SegmentQualityMetrics:
    """Metrics for evaluating segment quality"""
    k: int
    silhouette_score: float
    largest_segment_pct: float
    smallest_segment_pct: float
    segment_sizes: List[int]
    is_balanced: bool
    is_descriptive: bool  # Based on silhouette
    passes_quality_check: bool  # Overall pass/fail


class ImprovedClusteringEngine:
    """
    Improved clustering engine that produces balanced, descriptive segments.

    Fixes:
    - "Everyone vs outliers" problem via robust scaling
    - Degenerate k=2 clustering via higher min_k
    - Unbalanced segments via segment balance validation
    - Tiny segments via configurable minimum size
    """

    def __init__(self, config: Optional[ClusteringConfig] = None):
        self.config = config or ClusteringConfig.from_env()
        logger.info(f"Clustering config: min_k={self.config.min_k}, max_k={self.config.max_k}, "
                   f"max_dominant={self.config.max_dominant_segment_pct}%, "
                   f"min_segment={self.config.min_segment_size_pct}%")


    def preprocess_features(
        self,
        X: np.ndarray,
        axis_name: str
    ) -> Tuple[np.ndarray, Dict]:
        """
        Robust feature preprocessing to handle outliers.

        Steps:
        1. Winsorize extreme values (cap at percentile)
        2. Use RobustScaler (median/IQR) instead of StandardScaler (mean/std)
        3. Handle inf/nan values

        Returns:
            (X_preprocessed, preprocessing_params)
        """
        # Step 1: Handle inf/nan
        X_clean = np.nan_to_num(X, nan=0.0, posinf=np.nan, neginf=np.nan)

        # Step 2: Winsorize extreme values (per feature)
        X_winsorized = X_clean.copy()
        winsorize_limits = {}

        if self.config.enable_robust_scaling:
            for feat_idx in range(X_clean.shape[1]):
                feature_values = X_clean[:, feat_idx]
                # Remove nan values for percentile calculation
                valid_values = feature_values[~np.isnan(feature_values)]

                if len(valid_values) > 0:
                    lower_limit = np.percentile(valid_values, 100 - self.config.winsorize_percentile)
                    upper_limit = np.percentile(valid_values, self.config.winsorize_percentile)

                    # Cap values
                    X_winsorized[:, feat_idx] = np.clip(feature_values, lower_limit, upper_limit)

                    winsorize_limits[feat_idx] = {
                        'lower': float(lower_limit),
                        'upper': float(upper_limit)
                    }

        # Handle any remaining nan from clipping
        X_winsorized = np.nan_to_num(X_winsorized, nan=0.0)

        # Step 3: Robust scaling (median/IQR instead of mean/std)
        if self.config.enable_robust_scaling:
            scaler = RobustScaler()
            X_scaled = scaler.fit_transform(X_winsorized)

            scaler_params = {
                'type': 'robust',
                'center': scaler.center_.tolist(),
                'scale': scaler.scale_.tolist(),
                'winsorize_limits': winsorize_limits
            }
        else:
            # Fallback to standard scaling
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_winsorized)

            scaler_params = {
                'type': 'standard',
                'mean': scaler.mean_.tolist(),
                'scale': scaler.scale_.tolist(),
                'winsorize_limits': winsorize_limits
            }

        logger.info(f"{axis_name}: Preprocessed features with robust scaling, "
                   f"winsorized at {self.config.winsorize_percentile}th percentile")

        return X_scaled, scaler_params


    def evaluate_segment_balance(
        self,
        labels: np.ndarray,
        n_samples: int
    ) -> SegmentQualityMetrics:
        """
        Evaluate if segments are balanced (not "everyone vs outliers").

        Returns:
            SegmentQualityMetrics with balance assessment
        """
        # Count segment sizes
        segment_counts = Counter(labels)
        k = len(segment_counts)
        segment_sizes = list(segment_counts.values())

        # Calculate percentages
        largest_pct = max(segment_sizes) / n_samples * 100
        smallest_pct = min(segment_sizes) / n_samples * 100

        # Check balance constraints
        is_balanced = (
            largest_pct <= self.config.max_dominant_segment_pct and
            smallest_pct >= self.config.min_segment_size_pct
        )

        # Placeholder for silhouette (will be calculated separately)
        return SegmentQualityMetrics(
            k=k,
            silhouette_score=0.0,  # Will be filled in
            largest_segment_pct=largest_pct,
            smallest_segment_pct=smallest_pct,
            segment_sizes=segment_sizes,
            is_balanced=is_balanced,
            is_descriptive=True,  # Will be filled in
            passes_quality_check=is_balanced
        )


    def find_optimal_k_with_balance(
        self,
        X: np.ndarray,
        axis_name: str
    ) -> Tuple[int, float, SegmentQualityMetrics]:
        """
        Find optimal k that produces BOTH good clustering AND balanced segments.

        This is the key fix: we don't just optimize silhouette, we also ensure
        segments are balanced and descriptive.

        Returns:
            (optimal_k, silhouette_score, quality_metrics)
        """
        best_k = self.config.min_k
        best_silhouette = -1
        best_metrics = None

        logger.info(f"{axis_name}: Testing k-range [{self.config.min_k}, {self.config.max_k}] "
                   f"with balance constraints")

        for k in range(self.config.min_k, min(self.config.max_k + 1, len(X))):
            try:
                # Cluster
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = kmeans.fit_predict(X)

                # Evaluate clustering quality
                silhouette = silhouette_score(X, labels)

                # Evaluate segment balance
                metrics = self.evaluate_segment_balance(labels, len(X))
                metrics.silhouette_score = silhouette
                metrics.is_descriptive = silhouette >= self.config.min_silhouette
                metrics.passes_quality_check = metrics.is_balanced and metrics.is_descriptive

                logger.debug(f"{axis_name}: k={k}, silhouette={silhouette:.3f}, "
                            f"largest_seg={metrics.largest_segment_pct:.1f}%, "
                            f"smallest_seg={metrics.smallest_segment_pct:.1f}%, "
                            f"balanced={metrics.is_balanced}")

                # Prefer balanced + descriptive over just high silhouette
                if metrics.passes_quality_check:
                    if silhouette > best_silhouette:
                        best_silhouette = silhouette
                        best_k = k
                        best_metrics = metrics
                elif best_metrics is None:
                    # No balanced solution yet, keep best silhouette
                    if silhouette > best_silhouette:
                        best_silhouette = silhouette
                        best_k = k
                        best_metrics = metrics

            except Exception as e:
                logger.warning(f"{axis_name}: Failed to evaluate k={k}: {e}")
                continue

        if best_metrics and not best_metrics.passes_quality_check:
            logger.warning(
                f"{axis_name}: No balanced solution found! Best k={best_k} has "
                f"{best_metrics.largest_segment_pct:.1f}% in largest segment "
                f"(max allowed: {self.config.max_dominant_segment_pct}%)"
            )
        else:
            logger.info(
                f"{axis_name}: ✅ Found balanced clustering k={best_k}, "
                f"silhouette={best_silhouette:.3f}, "
                f"largest_seg={best_metrics.largest_segment_pct:.1f}%"
            )

        return best_k, best_silhouette, best_metrics


    def cluster_with_quality_validation(
        self,
        X: np.ndarray,
        axis_name: str
    ) -> Tuple[np.ndarray, KMeans, SegmentQualityMetrics]:
        """
        Complete clustering pipeline with preprocessing and validation.

        Returns:
            (labels, kmeans_model, quality_metrics)
        """
        # Step 1: Preprocess features (robust scaling, outlier handling)
        X_preprocessed, scaler_params = self.preprocess_features(X, axis_name)

        # Step 2: Find optimal k with balance validation
        optimal_k, silhouette, metrics = self.find_optimal_k_with_balance(
            X_preprocessed,
            axis_name
        )

        # Step 3: Final clustering with optimal k
        kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_preprocessed)

        # Step 4: Validate final result
        final_metrics = self.evaluate_segment_balance(labels, len(X))
        final_metrics.silhouette_score = silhouette
        final_metrics.is_descriptive = silhouette >= self.config.min_silhouette
        final_metrics.passes_quality_check = final_metrics.is_balanced and final_metrics.is_descriptive

        return labels, kmeans, final_metrics


def generate_clustering_quality_report(
    axis_results: Dict[str, SegmentQualityMetrics]
) -> str:
    """
    Generate a human-readable quality report.

    Args:
        axis_results: {axis_name: SegmentQualityMetrics}

    Returns:
        Formatted report string
    """
    report = []
    report.append("=" * 70)
    report.append("CLUSTERING QUALITY REPORT")
    report.append("=" * 70)

    # Summary stats
    total_axes = len(axis_results)
    balanced_axes = sum(1 for m in axis_results.values() if m.is_balanced)
    descriptive_axes = sum(1 for m in axis_results.values() if m.is_descriptive)
    passing_axes = sum(1 for m in axis_results.values() if m.passes_quality_check)

    report.append(f"\nOverall: {passing_axes}/{total_axes} axes passed quality checks")
    report.append(f"Balanced: {balanced_axes}/{total_axes}")
    report.append(f"Descriptive: {descriptive_axes}/{total_axes}")

    # Per-axis details
    report.append("\nPer-Axis Results:")
    report.append("-" * 70)

    for axis_name, metrics in sorted(axis_results.items()):
        status = "✅ PASS" if metrics.passes_quality_check else "⚠️  WARN"
        report.append(f"\n{status} {axis_name}:")
        report.append(f"  k={metrics.k}, silhouette={metrics.silhouette_score:.3f}")
        report.append(f"  Largest segment: {metrics.largest_segment_pct:.1f}%")
        report.append(f"  Smallest segment: {metrics.smallest_segment_pct:.1f}%")
        report.append(f"  Segment sizes: {metrics.segment_sizes}")

        if not metrics.is_balanced:
            report.append(f"  ⚠️  UNBALANCED: Largest segment exceeds threshold")
        if not metrics.is_descriptive:
            report.append(f"  ⚠️  LOW SILHOUETTE: Segments not well-separated")

    report.append("\n" + "=" * 70)

    return "\n".join(report)
