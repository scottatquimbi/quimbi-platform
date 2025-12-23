"""
Dynamic K-Range Optimization for Clustering

Automatically determines the optimal number of clusters (k) for each behavioral axis
based on data characteristics, rather than using a fixed k-range (2-6).

Key Features:
- Data-driven k selection using multiple quality metrics
- Adaptive to different axes (some may need 3 clusters, others may need 8)
- Prevents over-segmentation (too many clusters) and under-segmentation (too few)
- Feature-flagged: can fall back to fixed k-range (2-6)

Methods:
1. Elbow Method: Find "elbow" in inertia curve
2. Silhouette Analysis: Maximize average silhouette score
3. Gap Statistic: Compare inertia to null distribution
4. Calinski-Harabasz Index: Maximize between-cluster vs within-cluster variance
"""

import os
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score
import logging

logger = logging.getLogger(__name__)


@dataclass
class KOptimizationResult:
    """Result from k-range optimization"""
    optimal_k: int
    k_range_tested: Tuple[int, int]  # (min_k, max_k)
    scores: Dict[int, Dict[str, float]]  # {k: {metric: score}}
    method_used: str
    confidence: float  # 0-1 (how confident we are in this k)
    recommendation: str


class DynamicKOptimizerConfig:
    """Configuration for dynamic k optimization"""

    def __init__(
        self,
        enabled: bool = False,  # Disabled by default (experimental)
        min_k: int = 2,
        max_k: int = 10,  # Increased from fixed 6
        adaptive_max_k: bool = True,  # Adjust max_k based on data size
        min_samples_per_cluster: int = 50,  # Minimum samples per cluster
        silhouette_threshold: float = 0.3,  # Min silhouette score
        use_elbow_method: bool = True,
        use_silhouette_method: bool = True,
        use_gap_statistic: bool = False,  # More expensive
        use_calinski_harabasz: bool = True,
    ):
        self.enabled = enabled
        self.min_k = min_k
        self.max_k = max_k
        self.adaptive_max_k = adaptive_max_k
        self.min_samples_per_cluster = min_samples_per_cluster
        self.silhouette_threshold = silhouette_threshold
        self.use_elbow_method = use_elbow_method
        self.use_silhouette_method = use_silhouette_method
        self.use_gap_statistic = use_gap_statistic
        self.use_calinski_harabasz = use_calinski_harabasz

    @classmethod
    def from_env(cls) -> "DynamicKOptimizerConfig":
        """Load configuration from environment variables"""
        return cls(
            enabled=os.getenv("ENABLE_DYNAMIC_K_RANGE", "false").lower() == "true",
            min_k=int(os.getenv("DYNAMIC_K_MIN", "2")),
            max_k=int(os.getenv("DYNAMIC_K_MAX", "10")),
            adaptive_max_k=os.getenv("DYNAMIC_K_ADAPTIVE", "true").lower() == "true",
            min_samples_per_cluster=int(os.getenv("DYNAMIC_K_MIN_SAMPLES", "50")),
            silhouette_threshold=float(os.getenv("DYNAMIC_K_SILHOUETTE_THRESHOLD", "0.3")),
        )


class DynamicKOptimizer:
    """
    Dynamically determines optimal number of clusters for an axis.

    This replaces the fixed k-range (2-6) with a data-driven approach.
    Each behavioral axis may have a different optimal k.
    """

    def __init__(self, config: Optional[DynamicKOptimizerConfig] = None):
        self.config = config or DynamicKOptimizerConfig.from_env()

    def find_optimal_k(
        self,
        X: np.ndarray,
        axis_name: str = "unknown"
    ) -> KOptimizationResult:
        """
        Find optimal number of clusters for the data.

        Args:
            X: Feature matrix (n_samples, n_features)
            axis_name: Name of behavioral axis (for logging)

        Returns:
            KOptimizationResult with recommended k
        """
        if not self.config.enabled:
            # Fall back to fixed k-range
            return self._fallback_fixed_k(X, axis_name)

        n_samples = X.shape[0]

        # Determine max_k based on data size
        max_k = self._determine_max_k(n_samples)

        logger.info(f"Finding optimal k for {axis_name} (n={n_samples}, k_range={self.config.min_k}-{max_k})")

        # Test multiple k values
        k_range = range(self.config.min_k, max_k + 1)
        scores = {}

        for k in k_range:
            scores[k] = self._evaluate_k(X, k)

        # Combine methods to select optimal k
        optimal_k, confidence = self._select_optimal_k(scores, X.shape[0])

        # Generate recommendation
        recommendation = self._generate_recommendation(optimal_k, scores, axis_name)

        return KOptimizationResult(
            optimal_k=optimal_k,
            k_range_tested=(self.config.min_k, max_k),
            scores=scores,
            method_used="ensemble" if len(scores) > 1 else "silhouette",
            confidence=confidence,
            recommendation=recommendation
        )

    def _determine_max_k(self, n_samples: int) -> int:
        """
        Determine maximum k based on data size.

        Rule of thumb: max_k = sqrt(n / 2) but capped
        Example:
        - 100 customers: max_k = 7
        - 1000 customers: max_k = 22 → capped at config.max_k
        - 10000 customers: max_k = 70 → capped at config.max_k
        """
        if not self.config.adaptive_max_k:
            return self.config.max_k

        # Calculate based on sample size
        theoretical_max = int(np.sqrt(n_samples / 2))

        # Ensure minimum samples per cluster
        max_k_by_samples = n_samples // self.config.min_samples_per_cluster

        # Take minimum of theoretical max, samples constraint, and config max
        max_k = min(theoretical_max, max_k_by_samples, self.config.max_k)

        # Ensure at least min_k
        max_k = max(max_k, self.config.min_k)

        return max_k

    def _evaluate_k(self, X: np.ndarray, k: int) -> Dict[str, float]:
        """
        Evaluate clustering quality for a specific k.

        Returns dict of metrics: {metric_name: score}
        """
        scores = {}

        try:
            # Fit KMeans
            kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = kmeans.fit_predict(X)

            # Calculate metrics
            if self.config.use_silhouette_method:
                scores['silhouette'] = silhouette_score(X, labels)

            if self.config.use_calinski_harabasz:
                scores['calinski_harabasz'] = calinski_harabasz_score(X, labels)

            if self.config.use_elbow_method:
                scores['inertia'] = kmeans.inertia_
                scores['inertia_normalized'] = kmeans.inertia_ / X.shape[0]

            # Check cluster sizes
            unique, counts = np.unique(labels, return_counts=True)
            min_cluster_size = counts.min()
            scores['min_cluster_size'] = min_cluster_size
            scores['cluster_balance'] = counts.std() / counts.mean()  # Lower = better balance

        except Exception as e:
            logger.warning(f"Failed to evaluate k={k}: {e}")
            scores['error'] = 1.0

        return scores

    def _select_optimal_k(
        self,
        scores: Dict[int, Dict[str, float]],
        n_samples: int
    ) -> Tuple[int, float]:
        """
        Select optimal k from evaluated scores using ensemble method.

        Returns: (optimal_k, confidence)
        """
        k_values = sorted(scores.keys())

        # Method 1: Best silhouette score WITH balance penalty
        # Goal: Maximize explanatory power, not just cluster tightness
        optimal_k_silhouette = None
        best_score = -1

        if self.config.use_silhouette_method:
            logger.info(f"Evaluating k values with balance-aware scoring:")
            for k in k_values:
                sil = scores[k].get('silhouette', 0)
                balance = scores[k].get('cluster_balance', 1.0)

                # Balance-aware scoring: Prioritize explanatory power over cluster tightness
                # balance = std/mean, so 0.0 = perfect balance, higher = worse
                # Formula: 40% silhouette quality + 60% balance quality
                # This ensures segments are actionable, not just mathematically tight
                balance_quality = 1.0 - min(1.0, balance)  # Invert: higher balance = lower quality
                combined_score = (0.4 * sil) + (0.6 * balance_quality)

                logger.info(f"  k={k}: sil={sil:.3f}, balance={balance:.3f}, bal_qual={balance_quality:.3f}, combined={combined_score:.3f}")

                if combined_score > best_score and sil >= self.config.silhouette_threshold:
                    best_score = combined_score
                    optimal_k_silhouette = k

            logger.info(f"Best k by silhouette+balance: k={optimal_k_silhouette} (score={best_score:.3f})")

        # Method 2: Elbow method (find elbow in inertia curve)
        optimal_k_elbow = None
        if self.config.use_elbow_method:
            optimal_k_elbow = self._find_elbow_point(scores, k_values)

        # Method 3: Calinski-Harabasz Index WITH balance awareness (higher is better)
        optimal_k_ch = None
        if self.config.use_calinski_harabasz:
            best_ch = -1
            for k in k_values:
                ch = scores[k].get('calinski_harabasz', 0)
                balance = scores[k].get('cluster_balance', 1.0)

                # Normalize CH score to 0-1 range (divide by max observed)
                ch_normalized = ch / max([scores[kk].get('calinski_harabasz', 1) for kk in k_values])

                # Same balance-aware scoring: 40% CH + 60% balance
                balance_quality = 1.0 - min(1.0, balance)
                combined_score = (0.4 * ch_normalized) + (0.6 * balance_quality)

                if combined_score > best_ch:
                    best_ch = combined_score
                    optimal_k_ch = k

        # Ensemble: Majority vote
        candidates = [k for k in [optimal_k_silhouette, optimal_k_elbow, optimal_k_ch] if k is not None]

        if not candidates:
            # Fallback to middle of range
            optimal_k = k_values[len(k_values) // 2]
            confidence = 0.3
        else:
            # Most common k (mode)
            from collections import Counter
            counter = Counter(candidates)
            optimal_k = counter.most_common(1)[0][0]

            # Confidence based on agreement
            agreement_ratio = counter[optimal_k] / len(candidates)
            silhouette_score = scores[optimal_k].get('silhouette', 0)

            # Combine agreement and silhouette for confidence
            confidence = min(1.0, 0.5 * agreement_ratio + 0.5 * silhouette_score)

        return optimal_k, confidence

    def _find_elbow_point(
        self,
        scores: Dict[int, Dict[str, float]],
        k_values: List[int]
    ) -> Optional[int]:
        """
        Find elbow point in inertia curve.

        Uses angle method: find k where angle between
        (k-1, k) and (k, k+1) is sharpest.
        """
        if len(k_values) < 3:
            return None

        inertias = [scores[k].get('inertia', 0) for k in k_values]

        # Calculate angles
        angles = []
        for i in range(1, len(k_values) - 1):
            # Vector from k-1 to k
            v1 = np.array([1, inertias[i] - inertias[i-1]])
            # Vector from k to k+1
            v2 = np.array([1, inertias[i+1] - inertias[i]])

            # Angle between vectors
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            angle = np.arccos(np.clip(cos_angle, -1, 1))
            angles.append(angle)

        if angles:
            # Elbow is where angle is smallest (sharpest turn)
            elbow_idx = np.argmin(angles) + 1  # +1 because angles start at index 1
            return k_values[elbow_idx]

        return None

    def _generate_recommendation(
        self,
        optimal_k: int,
        scores: Dict[int, Dict[str, float]],
        axis_name: str
    ) -> str:
        """Generate human-readable recommendation"""
        k_scores = scores[optimal_k]

        silhouette = k_scores.get('silhouette', 0)
        min_size = k_scores.get('min_cluster_size', 0)

        recommendation = f"Recommended k={optimal_k} for {axis_name}. "

        if silhouette >= 0.5:
            recommendation += "Strong cluster separation (silhouette >= 0.5). "
        elif silhouette >= self.config.silhouette_threshold:
            recommendation += "Moderate cluster separation. "
        else:
            recommendation += f"⚠️  Weak cluster separation (silhouette={silhouette:.2f} < {self.config.silhouette_threshold}). "
            recommendation += "Consider reviewing axis features or using fewer clusters. "

        if min_size < self.config.min_samples_per_cluster:
            recommendation += f"⚠️  Small clusters detected (min size: {min_size}). "

        return recommendation

    def _fallback_fixed_k(self, X: np.ndarray, axis_name: str) -> KOptimizationResult:
        """
        Fallback to original fixed k-range (2-6) behavior.

        Used when dynamic k optimization is disabled.
        """
        # Test k=2 through k=6
        k_range = range(2, 7)
        scores = {}

        for k in k_range:
            scores[k] = self._evaluate_k(X, k)

        # Select k with best silhouette score >= threshold
        best_k = 2
        best_silhouette = -1

        for k in k_range:
            sil = scores[k].get('silhouette', 0)
            if sil >= 0.3 and sil > best_silhouette:
                best_silhouette = sil
                best_k = k

        return KOptimizationResult(
            optimal_k=best_k,
            k_range_tested=(2, 6),
            scores=scores,
            method_used="fixed_range_silhouette",
            confidence=best_silhouette if best_silhouette > 0 else 0.5,
            recommendation=f"Using fixed k-range (2-6). Selected k={best_k} with silhouette={best_silhouette:.2f}"
        )

    def optimize_all_axes(
        self,
        axes_data: Dict[str, np.ndarray]
    ) -> Dict[str, KOptimizationResult]:
        """
        Optimize k for multiple behavioral axes.

        Args:
            axes_data: {axis_name: feature_matrix}

        Returns:
            {axis_name: KOptimizationResult}
        """
        results = {}

        for axis_name, X in axes_data.items():
            logger.info(f"Optimizing k for axis: {axis_name}")
            results[axis_name] = self.find_optimal_k(X, axis_name)

        return results

    def get_optimization_summary(
        self,
        results: Dict[str, KOptimizationResult]
    ) -> Dict[str, Any]:
        """
        Generate summary statistics for k optimization across all axes.

        Returns insights about:
        - Average optimal k
        - k distribution
        - Confidence levels
        - Axes needing review
        """
        if not results:
            return {"error": "No optimization results"}

        optimal_ks = [r.optimal_k for r in results.values()]
        confidences = [r.confidence for r in results.values()]

        # Find axes with low confidence
        low_confidence_axes = [
            (axis, result.optimal_k, result.confidence)
            for axis, result in results.items()
            if result.confidence < 0.5
        ]

        # Find axes with many clusters
        high_k_axes = [
            (axis, result.optimal_k)
            for axis, result in results.items()
            if result.optimal_k > 6
        ]

        return {
            "total_axes": len(results),
            "avg_optimal_k": np.mean(optimal_ks),
            "median_optimal_k": np.median(optimal_ks),
            "k_distribution": dict(zip(*np.unique(optimal_ks, return_counts=True))),
            "avg_confidence": np.mean(confidences),
            "low_confidence_axes": low_confidence_axes,  # Need review
            "high_k_axes": high_k_axes,  # Complex behavior patterns
            "method_enabled": self.config.enabled,
        }
