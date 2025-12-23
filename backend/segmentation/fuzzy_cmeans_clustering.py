"""
Fuzzy C-Means Clustering for E-Commerce Segmentation

Replaces hard K-means with proper Fuzzy C-Means algorithm.

FCM is MUCH better for e-commerce because:
1. Natural soft membership (no post-hoc fuzzy conversion)
2. Handles overlapping segments better
3. Less sensitive to outliers
4. Works better with skewed distributions

Author: Quimbi Platform
Date: 2025-12-14
"""

import numpy as np
import os
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
import logging
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)


@dataclass
class FCMConfig:
    """Configuration for Fuzzy C-Means clustering"""

    # FCM-specific parameters
    m: float = 2.0  # Fuzziness parameter (1.5-3.0, higher = fuzzier)
    max_iter: int = 150
    error_threshold: float = 1e-5

    # K-range selection
    min_k: int = 3
    max_k: int = 7

    # Quality thresholds
    min_silhouette: float = 0.30
    max_dominant_segment_pct: float = 55.0  # Slightly more lenient than K-means
    min_segment_size_pct: float = 3.0

    # Outlier preprocessing
    enable_robust_scaling: bool = True
    winsorize_percentile: float = 99.0

    @classmethod
    def from_env(cls) -> 'FCMConfig':
        """Load from environment variables"""
        return cls(
            m=float(os.getenv("FCM_FUZZINESS", "2.0")),
            max_iter=int(os.getenv("FCM_MAX_ITER", "150")),
            error_threshold=float(os.getenv("FCM_ERROR_THRESHOLD", "1e-5")),
            min_k=int(os.getenv("CLUSTERING_MIN_K", "3")),
            max_k=int(os.getenv("CLUSTERING_MAX_K", "7")),
            min_silhouette=float(os.getenv("CLUSTERING_MIN_SILHOUETTE", "0.30")),
            max_dominant_segment_pct=float(os.getenv("CLUSTERING_MAX_DOMINANT_PCT", "55.0")),
            min_segment_size_pct=float(os.getenv("CLUSTERING_MIN_SEGMENT_PCT", "3.0")),
            enable_robust_scaling=os.getenv("CLUSTERING_ROBUST_SCALING", "true").lower() == "true",
            winsorize_percentile=float(os.getenv("CLUSTERING_WINSORIZE_PCT", "99.0")),
        )


class FuzzyCMeans:
    """
    Fuzzy C-Means clustering implementation.

    Unlike K-means, FCM:
    - Gives soft (fuzzy) membership to ALL clusters
    - Less sensitive to initialization
    - Handles overlapping clusters better
    - Works better with skewed data

    Algorithm:
    1. Initialize cluster centers randomly
    2. Calculate fuzzy membership for each point to each cluster
    3. Update cluster centers based on weighted membership
    4. Repeat until convergence
    """

    def __init__(self, n_clusters: int = 3, m: float = 2.0, max_iter: int = 150,
                 error: float = 1e-5, random_state: int = 42):
        """
        Initialize Fuzzy C-Means.

        Args:
            n_clusters: Number of clusters (c)
            m: Fuzziness parameter (1 < m < ∞, typically 2.0)
                - m=1: Hard clustering (like K-means)
                - m=2: Moderate fuzzy (recommended)
                - m>3: Very fuzzy (blurred clusters)
            max_iter: Maximum iterations
            error: Convergence threshold
            random_state: Random seed
        """
        self.n_clusters = n_clusters
        self.m = m
        self.max_iter = max_iter
        self.error = error
        self.random_state = random_state

        # Fitted values
        self.cluster_centers_ = None
        self.u_ = None  # Fuzzy membership matrix
        self.n_iter_ = 0


    def _initialize_membership(self, n_samples: int) -> np.ndarray:
        """
        Initialize fuzzy membership matrix randomly.

        Returns:
            u: (n_samples, n_clusters) matrix where each row sums to 1
        """
        np.random.seed(self.random_state)
        u = np.random.rand(n_samples, self.n_clusters)

        # Normalize rows to sum to 1
        u = u / np.sum(u, axis=1, keepdims=True)

        return u


    def _calculate_cluster_centers(self, X: np.ndarray, u: np.ndarray) -> np.ndarray:
        """
        Calculate cluster centers based on fuzzy membership.

        Formula: c_j = Σ(u_ij^m * x_i) / Σ(u_ij^m)

        Returns:
            centers: (n_clusters, n_features) array
        """
        um = u ** self.m  # Apply fuzziness

        centers = []
        for j in range(self.n_clusters):
            # Weighted average of all points, weighted by fuzzy membership
            center = np.sum(um[:, j:j+1] * X, axis=0) / np.sum(um[:, j])
            centers.append(center)

        return np.array(centers)


    def _calculate_distances(self, X: np.ndarray, centers: np.ndarray) -> np.ndarray:
        """
        Calculate distances from each point to each cluster center.

        Returns:
            distances: (n_samples, n_clusters) array
        """
        distances = np.zeros((X.shape[0], self.n_clusters))

        for j in range(self.n_clusters):
            # Euclidean distance
            distances[:, j] = np.linalg.norm(X - centers[j], axis=1)

        return distances


    def _update_membership(self, distances: np.ndarray) -> np.ndarray:
        """
        Update fuzzy membership matrix based on distances.

        Formula: u_ij = 1 / Σ_k (d_ij / d_ik)^(2/(m-1))

        Returns:
            u: (n_samples, n_clusters) matrix
        """
        # Handle zero distances (point exactly at center)
        distances = np.fmax(distances, 1e-10)

        # Calculate power
        power = 2.0 / (self.m - 1)

        # Calculate membership
        u = np.zeros((distances.shape[0], self.n_clusters))

        for j in range(self.n_clusters):
            # For each cluster j, calculate membership
            distance_ratios = distances[:, j:j+1] / distances
            u[:, j] = 1.0 / np.sum(distance_ratios ** power, axis=1)

        return u


    def fit(self, X: np.ndarray) -> 'FuzzyCMeans':
        """
        Fit Fuzzy C-Means to data.

        Args:
            X: (n_samples, n_features) array

        Returns:
            self
        """
        n_samples = X.shape[0]

        # Initialize membership matrix
        u = self._initialize_membership(n_samples)

        # Iterate until convergence
        for iteration in range(self.max_iter):
            u_old = u.copy()

            # Update cluster centers
            centers = self._calculate_cluster_centers(X, u)

            # Calculate distances
            distances = self._calculate_distances(X, centers)

            # Update membership
            u = self._update_membership(distances)

            # Check convergence
            diff = np.linalg.norm(u - u_old)

            if diff < self.error:
                logger.debug(f"FCM converged after {iteration + 1} iterations (diff={diff:.6f})")
                break

        self.cluster_centers_ = centers
        self.u_ = u
        self.n_iter_ = iteration + 1

        return self


    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict hard cluster labels (for compatibility with K-means API).

        Returns:
            labels: (n_samples,) array of cluster indices
        """
        if self.u_ is None:
            raise ValueError("Model not fitted yet. Call fit() first.")

        # Return cluster with maximum membership
        return np.argmax(self.u_, axis=1)


    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Get fuzzy membership probabilities.

        Returns:
            u: (n_samples, n_clusters) fuzzy membership matrix
        """
        if self.cluster_centers_ is None:
            raise ValueError("Model not fitted yet. Call fit() first.")

        # Calculate distances to centers
        distances = self._calculate_distances(X, self.cluster_centers_)

        # Calculate membership
        u = self._update_membership(distances)

        return u


    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        """Fit and predict hard labels."""
        self.fit(X)
        return self.predict(X)


class FuzzyCMeansEngine:
    """
    Complete FCM-based clustering engine with preprocessing and validation.

    This replaces the K-means implementation in ecommerce_clustering_engine.py
    with proper Fuzzy C-Means for better e-commerce segmentation.
    """

    def __init__(self, config: Optional[FCMConfig] = None):
        self.config = config or FCMConfig.from_env()
        logger.info(f"FCM Engine: m={self.config.m}, k=[{self.config.min_k}, {self.config.max_k}], "
                   f"max_dominant={self.config.max_dominant_segment_pct}%")


    def preprocess_features(self, X: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """Robust preprocessing with outlier handling."""
        # Winsorize
        X_clean = np.nan_to_num(X, nan=0.0, posinf=np.nan, neginf=np.nan)
        X_winsorized = X_clean.copy()

        winsorize_limits = {}
        if self.config.enable_robust_scaling:
            for feat_idx in range(X_clean.shape[1]):
                feature_values = X_clean[:, feat_idx]
                valid_values = feature_values[~np.isnan(feature_values)]

                if len(valid_values) > 0:
                    lower_limit = np.percentile(valid_values, 100 - self.config.winsorize_percentile)
                    upper_limit = np.percentile(valid_values, self.config.winsorize_percentile)
                    X_winsorized[:, feat_idx] = np.clip(feature_values, lower_limit, upper_limit)
                    winsorize_limits[feat_idx] = {'lower': float(lower_limit), 'upper': float(upper_limit)}

        X_winsorized = np.nan_to_num(X_winsorized, nan=0.0)

        # Robust scaling
        scaler = RobustScaler()
        X_scaled = scaler.fit_transform(X_winsorized)

        scaler_params = {
            'type': 'robust',
            'center': scaler.center_.tolist(),
            'scale': scaler.scale_.tolist(),
            'winsorize_limits': winsorize_limits
        }

        return X_scaled, scaler_params


    def evaluate_segment_balance(self, u: np.ndarray, threshold_type: str = 'hard') -> Dict:
        """
        Evaluate segment balance using fuzzy membership.

        Args:
            u: Fuzzy membership matrix (n_samples, n_clusters)
            threshold_type: 'hard' (max membership) or 'soft' (weighted)
        """
        n_samples = u.shape[0]

        if threshold_type == 'hard':
            # Count based on max membership (hard assignment)
            labels = np.argmax(u, axis=1)
            segment_sizes = [np.sum(labels == i) for i in range(u.shape[1])]
        else:
            # Sum fuzzy memberships (soft count)
            segment_sizes = np.sum(u, axis=0).tolist()

        largest_pct = max(segment_sizes) / n_samples * 100
        smallest_pct = min(segment_sizes) / n_samples * 100

        is_balanced = (
            largest_pct <= self.config.max_dominant_segment_pct and
            smallest_pct >= self.config.min_segment_size_pct
        )

        return {
            'segment_sizes': segment_sizes,
            'largest_pct': largest_pct,
            'smallest_pct': smallest_pct,
            'is_balanced': is_balanced
        }


    def find_optimal_k(self, X: np.ndarray, axis_name: str) -> Tuple[int, float, FuzzyCMeans]:
        """
        Find optimal k using FCM and silhouette score + balance validation.
        """
        best_k = self.config.min_k
        best_silhouette = -1
        best_model = None
        best_is_balanced = False

        logger.info(f"{axis_name}: Testing FCM with k=[{self.config.min_k}, {self.config.max_k}]")

        for k in range(self.config.min_k, min(self.config.max_k + 1, len(X))):
            try:
                # Fit FCM
                fcm = FuzzyCMeans(
                    n_clusters=k,
                    m=self.config.m,
                    max_iter=self.config.max_iter,
                    error=self.config.error_threshold,
                    random_state=42
                )
                fcm.fit(X)

                # Get hard labels for silhouette
                labels = fcm.predict(X)

                # Calculate silhouette
                silhouette = silhouette_score(X, labels)

                # Check balance
                balance = self.evaluate_segment_balance(fcm.u_, threshold_type='hard')

                logger.debug(f"{axis_name}: k={k}, silhouette={silhouette:.3f}, "
                            f"largest={balance['largest_pct']:.1f}%, "
                            f"balanced={balance['is_balanced']}")

                # Prefer balanced solutions
                if balance['is_balanced']:
                    if silhouette > best_silhouette or not best_is_balanced:
                        best_silhouette = silhouette
                        best_k = k
                        best_model = fcm
                        best_is_balanced = True
                elif not best_is_balanced and silhouette > best_silhouette:
                    best_silhouette = silhouette
                    best_k = k
                    best_model = fcm

            except Exception as e:
                logger.warning(f"{axis_name}: Failed k={k}: {e}")
                continue

        if not best_is_balanced:
            logger.warning(f"{axis_name}: No balanced solution found with FCM")
        else:
            logger.info(f"{axis_name}: ✅ FCM found balanced k={best_k}, silhouette={best_silhouette:.3f}")

        return best_k, best_silhouette, best_model


    def cluster_axis(self, X: np.ndarray, axis_name: str) -> Tuple[FuzzyCMeans, Dict]:
        """
        Complete FCM clustering pipeline for one axis.

        Returns:
            (fcm_model, metadata)
        """
        # Preprocess
        X_preprocessed, scaler_params = self.preprocess_features(X)

        # Find optimal k
        optimal_k, silhouette, fcm_model = self.find_optimal_k(X_preprocessed, axis_name)

        # Evaluate final quality
        balance = self.evaluate_segment_balance(fcm_model.u_)

        metadata = {
            'k': optimal_k,
            'silhouette': silhouette,
            'balance': balance,
            'scaler_params': scaler_params,
            'fuzziness_m': self.config.m,
            'n_iterations': fcm_model.n_iter_
        }

        return fcm_model, metadata
