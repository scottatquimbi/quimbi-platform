"""
Hierarchical Clustering - Recursive Subdivision of Broad Segments

Automatically detects when segments are too internally diverse (high variance)
and recursively subdivides them into meaningful sub-segments.

Use Cases:
1. One-time buyers (94%) split into: "bought yesterday" vs "bought 2 years ago"
2. Repeat buyers (6%) split into: Enterprise, Super-Engaged, Active, Occasional
3. Any segment with wide range from edge to center

Key Metrics to Detect "Too Broad":
- Intra-cluster variance (spread within the segment)
- Silhouette score (how well-separated from other segments)
- Diameter (max distance from edge to center)
- Population size (very large segments are suspect)
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging
from sklearn.metrics import silhouette_score, davies_bouldin_score

logger = logging.getLogger(__name__)


@dataclass
class SegmentDiversityMetrics:
    """Metrics to determine if a segment is too internally diverse"""
    segment_id: int
    customer_count: int

    # Variance metrics
    intra_cluster_variance: float  # Avg squared distance from center
    diameter: float                # Max distance between any two points
    avg_distance_to_center: float  # Mean distance from center

    # Spread metrics
    feature_ranges: Dict[str, float]  # {feature: max-min}
    feature_stds: Dict[str, float]    # {feature: std deviation}

    # Quality metrics
    cohesion: float  # How tightly clustered (lower = tighter)

    # Decision
    needs_subdivision: bool
    subdivision_reason: str


class HierarchicalClusteringEngine:
    """
    Recursively subdivide broad/diverse segments into sub-segments.

    Algorithm:
    1. Cluster data normally (get initial segments)
    2. For each segment, calculate diversity metrics
    3. If segment is "too broad", recursively cluster just that segment
    4. Repeat until all segments are cohesive or max depth reached
    """

    def __init__(
        self,
        # Subdivision triggers
        max_intra_variance: float = 2.0,      # Max variance before subdivision
        max_diameter_percentile: float = 95.0, # Max distance spread (percentile)
        min_segment_size_for_split: int = 100, # Don't split tiny segments
        max_segment_pct: float = 60.0,         # Max % before considering split

        # Recursion controls
        max_depth: int = 3,                    # Max levels of recursion
        min_subsegment_size: int = 30,         # Min customers per subsegment

        # Quality thresholds
        min_silhouette_improvement: float = 0.1  # Must improve by this much
    ):
        self.max_intra_variance = max_intra_variance
        self.max_diameter_percentile = max_diameter_percentile
        self.min_segment_size_for_split = min_segment_size_for_split
        self.max_segment_pct = max_segment_pct
        self.max_depth = max_depth
        self.min_subsegment_size = min_subsegment_size
        self.min_silhouette_improvement = min_silhouette_improvement


    def analyze_segment_diversity(
        self,
        X: np.ndarray,
        segment_mask: np.ndarray,
        cluster_center: np.ndarray,
        feature_names: List[str],
        total_population: int
    ) -> SegmentDiversityMetrics:
        """
        Calculate diversity metrics for a segment to determine if it needs subdivision.

        Args:
            X: Full feature matrix (n_samples, n_features)
            segment_mask: Boolean mask for this segment
            cluster_center: Center of this cluster
            feature_names: Names of features
            total_population: Total number of customers

        Returns:
            SegmentDiversityMetrics with subdivision decision
        """
        X_segment = X[segment_mask]
        n_customers = len(X_segment)

        if n_customers == 0:
            return SegmentDiversityMetrics(
                segment_id=0,
                customer_count=0,
                intra_cluster_variance=0.0,
                diameter=0.0,
                avg_distance_to_center=0.0,
                feature_ranges={},
                feature_stds={},
                cohesion=0.0,
                needs_subdivision=False,
                subdivision_reason="Empty segment"
            )

        # 1. Intra-cluster variance (avg squared distance from center)
        distances_to_center = np.linalg.norm(X_segment - cluster_center, axis=1)
        intra_variance = np.mean(distances_to_center ** 2)
        avg_distance = np.mean(distances_to_center)

        # 2. Diameter (max distance between any two points)
        # For efficiency, use max distance from center as approximation
        diameter = np.max(distances_to_center)

        # 3. Feature-wise spread
        feature_ranges = {}
        feature_stds = {}
        for i, fname in enumerate(feature_names):
            feature_vals = X_segment[:, i]
            feature_ranges[fname] = feature_vals.max() - feature_vals.min()
            feature_stds[fname] = feature_vals.std()

        # 4. Cohesion (normalized avg distance to center)
        cohesion = avg_distance

        # 5. Population percentage
        segment_pct = (n_customers / total_population) * 100

        # DECISION: Does this segment need subdivision?
        needs_subdivision = False
        reasons = []

        # Check 1: High intra-cluster variance
        if intra_variance > self.max_intra_variance:
            needs_subdivision = True
            reasons.append(f"High variance ({intra_variance:.2f} > {self.max_intra_variance})")

        # Check 2: Large diameter (wide spread)
        diameter_threshold = np.percentile(distances_to_center, self.max_diameter_percentile)
        if diameter > diameter_threshold * 1.5:
            needs_subdivision = True
            reasons.append(f"Wide diameter ({diameter:.2f} > {diameter_threshold*1.5:.2f})")

        # Check 3: Very large segment (might be hiding sub-groups)
        if segment_pct > self.max_segment_pct and n_customers > self.min_segment_size_for_split:
            needs_subdivision = True
            reasons.append(f"Large segment ({segment_pct:.1f}% > {self.max_segment_pct}%)")

        # Check 4: Must have enough customers to split
        if n_customers < self.min_segment_size_for_split:
            needs_subdivision = False
            reasons = ["Segment too small to split"]

        subdivision_reason = "; ".join(reasons) if reasons else "Cohesive segment"

        return SegmentDiversityMetrics(
            segment_id=0,
            customer_count=n_customers,
            intra_cluster_variance=intra_variance,
            diameter=diameter,
            avg_distance_to_center=avg_distance,
            feature_ranges=feature_ranges,
            feature_stds=feature_stds,
            cohesion=cohesion,
            needs_subdivision=needs_subdivision,
            subdivision_reason=subdivision_reason
        )


    def should_subdivide_segment(
        self,
        diversity: SegmentDiversityMetrics,
        current_depth: int
    ) -> bool:
        """
        Final decision on whether to subdivide a segment.

        Args:
            diversity: Diversity metrics for the segment
            current_depth: Current recursion depth

        Returns:
            True if should subdivide, False otherwise
        """
        # Don't subdivide if at max depth
        if current_depth >= self.max_depth:
            logger.info(f"Max depth {self.max_depth} reached, stopping subdivision")
            return False

        # Don't subdivide if segment too small
        if diversity.customer_count < self.min_segment_size_for_split:
            return False

        # Subdivide if diversity metrics indicate it's needed
        return diversity.needs_subdivision


    def recursive_cluster_segment(
        self,
        X: np.ndarray,
        segment_mask: np.ndarray,
        cluster_center: np.ndarray,
        feature_names: List[str],
        total_population: int,
        clustering_func,  # Function to re-cluster this segment
        current_depth: int = 0,
        parent_id: str = "root"
    ) -> List[Dict]:
        """
        Recursively subdivide a segment if it's too broad.

        Args:
            X: Full feature matrix
            segment_mask: Boolean mask for this segment
            cluster_center: Center of this segment
            feature_names: Feature names
            total_population: Total customer count
            clustering_func: Function(X_subset) -> labels that re-clusters the segment
            current_depth: Current recursion depth
            parent_id: ID of parent segment

        Returns:
            List of segment dictionaries with hierarchical structure
        """
        # Analyze diversity
        diversity = self.analyze_segment_diversity(
            X, segment_mask, cluster_center, feature_names, total_population
        )

        logger.info(
            f"Depth {current_depth}, Segment {parent_id}: "
            f"{diversity.customer_count} customers, "
            f"variance={diversity.intra_cluster_variance:.2f}, "
            f"diameter={diversity.diameter:.2f}"
        )

        # Decision: Should we subdivide?
        if not self.should_subdivide_segment(diversity, current_depth):
            logger.info(f"Segment {parent_id}: {diversity.subdivision_reason}")
            return [{
                'segment_id': parent_id,
                'depth': current_depth,
                'customer_count': diversity.customer_count,
                'diversity': diversity,
                'is_leaf': True,
                'subsegments': None
            }]

        # SUBDIVIDE: Re-cluster just this segment
        logger.info(f"Subdividing segment {parent_id}: {diversity.subdivision_reason}")

        X_segment = X[segment_mask]

        # Re-cluster this segment
        try:
            subsegment_labels = clustering_func(X_segment)
            n_subsegments = len(np.unique(subsegment_labels))

            logger.info(f"Subdivided into {n_subsegments} subsegments")

            # Recursively process each subsegment
            subsegments = []
            for subseg_id in range(n_subsegments):
                # Create mask for this subsegment (relative to X_segment)
                subseg_mask_local = (subsegment_labels == subseg_id)

                # Convert to global mask (relative to full X)
                global_indices = np.where(segment_mask)[0]
                subseg_mask_global = np.zeros(len(X), dtype=bool)
                subseg_mask_global[global_indices[subseg_mask_local]] = True

                # Calculate subsegment center
                subseg_center = X[subseg_mask_global].mean(axis=0)

                # Recursive call
                child_id = f"{parent_id}.{subseg_id}"
                subseg_results = self.recursive_cluster_segment(
                    X,
                    subseg_mask_global,
                    subseg_center,
                    feature_names,
                    total_population,
                    clustering_func,
                    current_depth + 1,
                    child_id
                )

                subsegments.extend(subseg_results)

            return [{
                'segment_id': parent_id,
                'depth': current_depth,
                'customer_count': diversity.customer_count,
                'diversity': diversity,
                'is_leaf': False,
                'subsegments': subsegments
            }]

        except Exception as e:
            logger.warning(f"Failed to subdivide segment {parent_id}: {e}")
            # Return as leaf segment if subdivision fails
            return [{
                'segment_id': parent_id,
                'depth': current_depth,
                'customer_count': diversity.customer_count,
                'diversity': diversity,
                'is_leaf': True,
                'subsegments': None,
                'subdivision_error': str(e)
            }]


    def flatten_hierarchy(self, hierarchy: List[Dict]) -> List[Dict]:
        """
        Flatten hierarchical segments into a list of leaf segments.

        Args:
            hierarchy: Hierarchical segment structure

        Returns:
            List of leaf segments only
        """
        leaves = []

        def extract_leaves(segments):
            for seg in segments:
                if seg.get('is_leaf', True):
                    leaves.append(seg)
                elif seg.get('subsegments'):
                    extract_leaves(seg['subsegments'])

        extract_leaves(hierarchy)
        return leaves
