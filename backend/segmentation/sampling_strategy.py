"""
Sampling Strategy for Weekly Clustering

Instead of clustering ALL customers every week, we:
1. Sample 1,000-2,000 customers per axis to discover segments
2. Once segments are discovered, assign ALL customers to segments using fuzzy membership
3. This reduces clustering time from hours to minutes

Key insight: Segment discovery is expensive (KMeans).
            Segment assignment is cheap (distance calculation).
"""
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class SmartSampler:
    """
    Intelligent sampling for clustering that ensures representative samples
    """

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def stratified_sample(
        self,
        customer_ids: List[str],
        customer_metadata: pd.DataFrame,
        sample_size: int = 1000,
        stratify_by: Optional[str] = None
    ) -> List[str]:
        """
        Sample customers using stratified sampling to ensure representation.

        Args:
            customer_ids: All customer IDs
            customer_metadata: DataFrame with customer info (order_count, total_value, etc.)
            sample_size: Number of customers to sample
            stratify_by: Column to stratify by (e.g., 'value_tier', 'activity_tier')

        Returns:
            List of sampled customer IDs
        """
        if len(customer_ids) <= sample_size:
            return customer_ids

        if stratify_by and stratify_by in customer_metadata.columns:
            # Stratified sampling - ensure we get customers from all tiers
            sampled = customer_metadata.groupby(stratify_by).apply(
                lambda x: x.sample(n=min(len(x), sample_size // customer_metadata[stratify_by].nunique()),
                                   random_state=self.random_seed)
            ).reset_index(drop=True)

            # If we didn't get enough, add more randomly
            if len(sampled) < sample_size:
                remaining = customer_metadata[~customer_metadata.index.isin(sampled.index)]
                additional = remaining.sample(n=sample_size - len(sampled), random_state=self.random_seed)
                sampled = pd.concat([sampled, additional])

            return sampled['customer_id'].tolist()
        else:
            # Simple random sampling
            return np.random.choice(customer_ids, size=sample_size, replace=False).tolist()

    def weighted_sample(
        self,
        customer_ids: List[str],
        customer_metadata: pd.DataFrame,
        sample_size: int = 1000,
        weight_by: str = 'total_value'
    ) -> List[str]:
        """
        Sample customers with probability proportional to a weight (e.g., purchase value).
        Ensures high-value customers are more likely to be included.

        Args:
            customer_ids: All customer IDs
            customer_metadata: DataFrame with customer info
            sample_size: Number of customers to sample
            weight_by: Column to use as weight

        Returns:
            List of sampled customer IDs
        """
        if len(customer_ids) <= sample_size:
            return customer_ids

        if weight_by in customer_metadata.columns:
            weights = customer_metadata[weight_by].values
            # Normalize weights to probabilities
            weights = weights / weights.sum()

            sampled_indices = np.random.choice(
                len(customer_ids),
                size=sample_size,
                replace=False,
                p=weights
            )

            return [customer_ids[i] for i in sampled_indices]
        else:
            # Fallback to random sampling
            return np.random.choice(customer_ids, size=sample_size, replace=False).tolist()

    def diverse_sample(
        self,
        customer_ids: List[str],
        customer_features: Dict[str, Dict[str, float]],
        sample_size: int = 1000,
        diversity_features: Optional[List[str]] = None
    ) -> List[str]:
        """
        Sample customers to maximize diversity in feature space.
        Uses k-means++ style initialization to spread samples across the space.

        Args:
            customer_ids: All customer IDs
            customer_features: Dict of {customer_id: {feature: value}}
            sample_size: Number of customers to sample
            diversity_features: Features to consider for diversity (None = all)

        Returns:
            List of sampled customer IDs
        """
        if len(customer_ids) <= sample_size:
            return customer_ids

        # Convert to feature matrix
        if diversity_features is None:
            # Use all features from first customer
            first_customer = list(customer_features.values())[0]
            diversity_features = list(first_customer.keys())

        feature_matrix = []
        valid_customer_ids = []

        for customer_id in customer_ids:
            if customer_id in customer_features:
                features = customer_features[customer_id]
                feature_vector = [features.get(f, 0.0) for f in diversity_features]
                feature_matrix.append(feature_vector)
                valid_customer_ids.append(customer_id)

        feature_matrix = np.array(feature_matrix)

        # Standardize features
        mean = feature_matrix.mean(axis=0)
        std = feature_matrix.std(axis=0) + 1e-10
        feature_matrix = (feature_matrix - mean) / std

        # k-means++ style sampling (maximizes diversity)
        sampled_indices = []
        remaining_indices = list(range(len(valid_customer_ids)))

        # First sample: random
        first_idx = np.random.choice(remaining_indices)
        sampled_indices.append(first_idx)
        remaining_indices.remove(first_idx)

        # Subsequent samples: farthest from existing samples
        for _ in range(min(sample_size - 1, len(remaining_indices))):
            # Calculate minimum distance to any sampled point
            distances = []
            for idx in remaining_indices:
                min_dist = min([
                    np.linalg.norm(feature_matrix[idx] - feature_matrix[sampled_idx])
                    for sampled_idx in sampled_indices
                ])
                distances.append(min_dist)

            # Sample proportional to distance (farther = more likely)
            distances = np.array(distances)
            probabilities = distances / distances.sum()

            next_idx = np.random.choice(remaining_indices, p=probabilities)
            sampled_indices.append(next_idx)
            remaining_indices.remove(next_idx)

        return [valid_customer_ids[i] for i in sampled_indices]


class AdaptiveSampler:
    """
    Adaptive sampling that adjusts sample size based on customer population and diversity
    """

    def __init__(self):
        self.sampler = SmartSampler()

    def calculate_optimal_sample_size(
        self,
        total_customers: int,
        min_sample: int = 500,
        max_sample: int = 5000,
        target_ratio: float = 0.05  # Sample 5% of population
    ) -> int:
        """
        Calculate optimal sample size based on population.

        For small populations (<10k): Sample 20-30%
        For medium populations (10k-100k): Sample 5-10%
        For large populations (>100k): Sample 2-5%
        """
        if total_customers < 10_000:
            # Small population: need more samples for stability
            sample_size = int(total_customers * 0.25)  # 25%
        elif total_customers < 100_000:
            # Medium population: 5-10%
            sample_size = int(total_customers * target_ratio)
        else:
            # Large population: 2-5%
            sample_size = int(total_customers * 0.03)

        # Clamp to min/max
        return max(min_sample, min(sample_size, max_sample))

    def sample_for_axis(
        self,
        axis_name: str,
        customer_ids: List[str],
        customer_metadata: pd.DataFrame,
        sample_size: Optional[int] = None
    ) -> List[str]:
        """
        Sample customers for a specific axis with axis-appropriate strategy.

        Different axes benefit from different sampling strategies:
        - Value axes (purchase_value): Weight by total spend
        - Frequency axes (purchase_frequency): Stratify by activity level
        - Behavioral axes: Diverse sampling
        """
        if sample_size is None:
            sample_size = self.calculate_optimal_sample_size(len(customer_ids))

        # Axis-specific sampling strategies
        if axis_name in ['purchase_value', 'customer_maturity']:
            # Weight by value - ensure high-value customers included
            return self.sampler.weighted_sample(
                customer_ids,
                customer_metadata,
                sample_size,
                weight_by='total_value'
            )

        elif axis_name in ['purchase_frequency', 'purchase_cadence']:
            # Stratify by activity level
            return self.sampler.stratified_sample(
                customer_ids,
                customer_metadata,
                sample_size,
                stratify_by='activity_tier'
            )

        elif axis_name in ['loyalty_trajectory', 'churn_risk']:
            # Include more recent customers (churn is time-sensitive)
            # Weight by recency
            customer_metadata['recency_weight'] = 1.0 / (customer_metadata['days_since_last_order'] + 1)
            return self.sampler.weighted_sample(
                customer_ids,
                customer_metadata,
                sample_size,
                weight_by='recency_weight'
            )

        else:
            # Default: diverse sampling for behavioral axes
            return self.sampler.stratified_sample(
                customer_ids,
                customer_metadata,
                sample_size,
                stratify_by='value_tier'
            )


# Production configuration
PRODUCTION_SAMPLING_CONFIG = {
    # Sample sizes per axis (can be different for each axis)
    'default_sample_size': 1500,  # Conservative default

    # Axis-specific overrides
    'axis_sample_sizes': {
        'purchase_value': 2000,  # More samples for value segmentation
        'loyalty_trajectory': 2500,  # More samples for churn prediction
        'purchase_frequency': 1500,
        'category_exploration': 1000,  # Less critical, fewer samples
        'return_behavior': 1000,  # Fewer customers have returns
    },

    # Minimum samples per segment (for quality)
    'min_samples_per_segment': 50,

    # Re-clustering schedule
    'full_recluster_frequency': 'monthly',  # Full population every month
    'sample_recluster_frequency': 'weekly',  # Sampled weekly

    # Sampling strategy per axis
    'sampling_strategies': {
        'purchase_value': 'weighted',  # Weight by value
        'purchase_frequency': 'stratified',  # Stratify by activity
        'loyalty_trajectory': 'recency_weighted',  # Weight by recency
        'default': 'diverse'  # Diverse sampling for others
    }
}


def estimate_runtime(
    num_stores: int,
    customers_per_store: int,
    num_axes: int = 13,
    use_sampling: bool = True,
    sample_size: int = 1500
) -> Dict[str, float]:
    """
    Estimate clustering runtime based on configuration.

    Benchmarks (based on your local results):
    - Feature extraction: ~80-100 customers/second
    - Clustering (KMeans): ~1-2 minutes per 1000 customers per axis
    - Assignment (after clustering): ~1000 customers/second

    Returns:
        Dictionary with time estimates in minutes
    """
    if use_sampling:
        # Sample-based clustering
        sample_feature_time = (sample_size / 90) / 60  # 90 customers/sec -> minutes
        sample_cluster_time = num_axes * (sample_size / 1000) * 1.5  # 1.5 min per 1k per axis

        # Assignment for all customers (fast)
        assignment_time = (customers_per_store / 1000) / 60  # 1000 customers/sec -> minutes

        total_per_store = sample_feature_time + sample_cluster_time + assignment_time
        total_all_stores = total_per_store * num_stores

        return {
            'per_store_minutes': round(total_per_store, 1),
            'total_minutes': round(total_all_stores, 1),
            'feature_extraction_minutes': round(sample_feature_time * num_stores, 1),
            'clustering_minutes': round(sample_cluster_time * num_stores, 1),
            'assignment_minutes': round(assignment_time * num_stores, 1),
        }
    else:
        # Full population clustering (what you just ran)
        full_feature_time = (customers_per_store / 90) / 60  # 90 customers/sec
        full_cluster_time = num_axes * (customers_per_store / 1000) * 1.5  # 1.5 min per 1k per axis

        total_per_store = full_feature_time + full_cluster_time
        total_all_stores = total_per_store * num_stores

        return {
            'per_store_minutes': round(total_per_store, 1),
            'total_minutes': round(total_all_stores, 1),
            'feature_extraction_minutes': round(full_feature_time * num_stores, 1),
            'clustering_minutes': round(full_cluster_time * num_stores, 1),
        }


if __name__ == "__main__":
    # Example usage
    print("Clustering Runtime Estimates\n" + "="*50)

    # Current: 1 store (Linda), 93k customers
    print("\nCurrent (1 store, 93k customers):")
    print("  Without sampling:", estimate_runtime(1, 93565, use_sampling=False))
    print("  With sampling (1.5k/axis):", estimate_runtime(1, 93565, use_sampling=True, sample_size=1500))

    # Future: 3 stores, 90k customers each
    print("\nNear future (3 stores, 90k each):")
    print("  Without sampling:", estimate_runtime(3, 90000, use_sampling=False))
    print("  With sampling (1.5k/axis):", estimate_runtime(3, 90000, use_sampling=True, sample_size=1500))

    # Growth: 5 stores, 100k customers each
    print("\nGrowth (5 stores, 100k each):")
    print("  Without sampling:", estimate_runtime(5, 100000, use_sampling=False))
    print("  With sampling (1.5k/axis):", estimate_runtime(5, 100000, use_sampling=True, sample_size=1500))
