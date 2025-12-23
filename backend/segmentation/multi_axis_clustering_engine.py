"""
Multi-Axis Clustering Engine

Discovers behavioral segments by clustering customers independently in each
feature space (axis). Uses fuzzy membership so customers belong to ALL segments
with varying strengths (0.0-1.0).

Core Algorithm:
1. Extract features for all customers across all axes
2. For each axis independently:
   - Normalize features
   - Find optimal k (number of clusters) using silhouette score
   - Cluster customers using KMeans
   - Calculate fuzzy membership (distance-based, sum to 1.0 per axis)
   - Interpret clusters (examine centroids, generate labels)
3. Store discovered segments and customer memberships

Author: Quimbi Platform
Version: 3.0.0 (Multi-Axis)
Date: October 14, 2025
"""

import numpy as np
import logging
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import statistics
import uuid
import json

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, davies_bouldin_score
from scipy.spatial.distance import mahalanobis, cdist
from scipy.stats import entropy

from backend.core.database import get_db_session
from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor as FeatureExtractor
from backend.segmentation.ai_segment_naming import name_segment_with_ai
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSegment:
    """A segment discovered within an axis"""
    segment_id: str
    axis_name: str
    segment_name: str
    cluster_center: np.ndarray
    feature_names: List[str]
    scaler_params: Dict[str, List[float]]  # Population scaler: {"mean": [...], "scale": [...]}
    population_percentage: float
    customer_count: int
    interpretation: str


@dataclass
class CustomerAxisProfile:
    """Customer's fuzzy membership profile for one axis"""
    customer_id: str
    axis_name: str
    memberships: Dict[str, float]  # {segment_name: membership_strength}
    dominant_segment: str
    features: Dict[str, float]
    calculated_at: datetime


@dataclass
class CustomerMultiAxisProfile:
    """Customer's complete profile across all axes"""
    customer_id: str
    store_id: str
    axis_profiles: Dict[str, CustomerAxisProfile]  # {axis_name: profile}
    dominant_segments: Dict[str, str]  # {axis_name: segment_name}

    # NEW: Fuzzy top-2 membership tracking (Phase 1: Combined Approach)
    fuzzy_memberships: Dict[str, Dict[str, float]] = field(default_factory=dict)  # {axis_name: {segment: score}}
    top2_segments: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)  # {axis_name: [(seg1, score1), (seg2, score2)]}
    membership_strength: Dict[str, str] = field(default_factory=dict)  # {axis_name: "strong"|"balanced"|"weak"}

    interpretation: str = ""
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MultiAxisClusteringEngine:
    """
    Discovers behavioral segments across multiple independent axes.

    Each axis is clustered separately to find natural behavioral patterns.
    Customers get fuzzy membership in all segments per axis.

    FIX: Clustering parameters are now configurable to support different stores
    and data-driven tuning.
    """

    def __init__(
        self,
        db_session=None,
        # Clustering parameters (configurable with sensible defaults)
        min_k: int = 2,
        max_k: int = 6,
        min_silhouette: float = 0.3,
        min_population: int = 100,
        # Session detection parameter
        session_gap_minutes: int = 30,
        # AI naming parameters
        use_ai_naming: bool = True,
        anthropic_api_key: Optional[str] = None
    ):
        """
        Initialize clustering engine with configurable parameters.

        Args:
            db_session: Database session (optional)
            min_k: Minimum clusters per axis (default: 2)
            max_k: Maximum clusters per axis (default: 6)
            min_silhouette: Minimum acceptable silhouette score (default: 0.3)
            min_population: Minimum customers required for discovery (default: 100)
            session_gap_minutes: Gap threshold for session detection (default: 30)
            use_ai_naming: Whether to use AI for segment naming (default: True)
            anthropic_api_key: Anthropic API key for AI naming (default: from env)
        """
        self.db_session = db_session

        # Feature extractor
        self.feature_extractor = FeatureExtractor()

        # Clustering parameters (now configurable)
        self.min_k = min_k
        self.max_k = max_k
        self.min_silhouette = min_silhouette
        self.min_population = min_population
        self.session_gap_minutes = session_gap_minutes  # Store for potential future use

        # AI naming
        self.use_ai_naming = use_ai_naming
        self.anthropic_api_key = anthropic_api_key or os.getenv('ANTHROPIC_API_KEY')


    async def discover_multi_axis_segments(
        self,
        store_id: str,
        store_launch_date: Optional[datetime] = None
    ) -> Dict[str, List[DiscoveredSegment]]:
        """
        Main entry point: Discover segments across all 13 e-commerce axes.

        Args:
            store_id: Store identifier
            store_launch_date: Launch date (for purchase timing axis, unused in e-commerce)

        Returns:
            Dict mapping axis name to list of discovered segments
        """
        logger.info(f"Starting multi-axis segmentation for store {store_id}")

        # Step 1: Fetch order data (e-commerce)
        order_data = await self._fetch_order_data(store_id)

        if len(order_data['customers']) < self.min_population:
            logger.warning(
                f"Insufficient population ({len(order_data['customers'])} customers)"
            )
            return {}

        logger.info(
            f"Loaded {len(order_data['orders'])} orders, {len(order_data['items'])} items "
            f"from {len(order_data['customers'])} customers"
        )

        # Step 2: Extract features for all customers across all axes
        extractor = FeatureExtractor()  # EcommerceFeatureExtractor
        all_customer_features = {}

        logger.info("Extracting features for all customers...")

        for customer_id in order_data['customers']:
            customer_orders = order_data['customer_orders'].get(customer_id, [])
            customer_items = order_data['customer_items'].get(customer_id, [])

            try:
                # Returns: {'purchase_frequency': {features}, 'purchase_value': {features}, ...}
                features = extractor.extract_all_features(
                    customer_id,
                    customer_orders,
                    customer_items
                )
                all_customer_features[customer_id] = features
            except Exception as e:
                logger.warning(f"Failed to extract features for {customer_id}: {e}")
                continue

        logger.info(f"Extracted features for {len(all_customer_features)} customers")

        # Step 3: Define 13 e-commerce axes
        axes = [
            'purchase_frequency',
            'purchase_value',
            'category_exploration',
            'price_sensitivity',
            'purchase_cadence',
            'customer_maturity',
            'repurchase_behavior',
            'return_behavior',
            'communication_preference',
            'problem_complexity_profile',
            'loyalty_trajectory',
            'product_knowledge',
            'value_sophistication'
            # Note: 'support_history' requires Gorgias data, skipped for now
        ]

        # Step 4: Cluster each axis independently
        all_segments = {}

        for axis_name in axes:
            logger.info(f"\n{'='*60}")
            logger.info(f"Clustering axis: {axis_name}")
            logger.info(f"{'='*60}")

            # Cluster this axis (using original method signature)
            try:
                segments = await self._cluster_axis(
                    axis_name,
                    all_customer_features,
                    store_id
                )

                if segments:
                    all_segments[axis_name] = segments
                    logger.info(
                        f"✓ {axis_name}: {len(segments)} segments discovered"
                    )
                else:
                    logger.warning(f"✗ {axis_name}: No segments discovered")

            except Exception as e:
                logger.error(f"Failed to cluster {axis_name}: {e}", exc_info=True)
                continue

        # Step 5: Store segments to database (DISABLED - we'll save to JSON instead)
        # if all_segments:
        #     await self._store_discovered_segments(store_id, all_segments)

        logger.info(f"\n{'='*60}")
        logger.info(
            f"Segmentation complete: {sum(len(s) for s in all_segments.values())} "
            f"segments across {len(all_segments)} axes"
        )
        logger.info(f"{'='*60}\n")

        return all_segments


    async def calculate_customer_profile(
        self,
        customer_id: str,
        store_id: str,
        store_launch_date: Optional[datetime] = None,
        store_profile: bool = False,
        segments_dict: Optional[Dict[str, List]] = None
    ) -> CustomerMultiAxisProfile:
        """
        Calculate individual customer's fuzzy membership profile across all axes.

        Args:
            customer_id: Customer identifier
            store_id: Store identifier
            store_launch_date: Launch date (for purchase timing)
            store_profile: If True, save profile to database
            segments_dict: Optional in-memory segments (avoids DB lookup)

        Returns:
            CustomerMultiAxisProfile with fuzzy memberships
        """
        logger.info(f"Calculating profile for customer {customer_id}")

        # Step 1: Get customer's orders and items (e-commerce specific)
        async with get_db_session() if not self.db_session else self._noop_context() as session:
            db = session or self.db_session

            # Convert customer_id to int (database column is bigint)
            customer_id_int = int(customer_id)

            # Fetch all customer data in one query
            query = text("""
                SELECT
                    order_id,
                    order_date,
                    order_total as total_price,
                    line_item_discount as discount_amount,
                    sales_channel as source,
                    product_id,
                    category,
                    product_type,
                    quantity,
                    line_item_sales as price,
                    line_item_refunds as refund_amount
                FROM combined_sales
                WHERE customer_id = :customer_id
                ORDER BY order_date
            """)
            result = await db.execute(query, {"customer_id": customer_id_int})
            rows = result.fetchall()

        if not rows:
            logger.warning(f"No orders found for customer {customer_id}")
            return None

        # Process rows into orders and items with proper type conversion
        orders_dict = {}
        customer_orders = []
        customer_items = []

        for row in rows:
            order_id = str(row.order_id)

            # Add order (avoid duplicates)
            if order_id not in orders_dict:
                order = {
                    'customer_id': customer_id,
                    'order_id': order_id,
                    'order_date': row.order_date,
                    'total_price': float(row.total_price or 0),
                    'discount_amount': float(row.discount_amount or 0),
                    'source': row.source
                }
                orders_dict[order_id] = order
                customer_orders.append(order)

            # Add item (with proper type conversion)
            if row.product_id:
                item = {
                    'customer_id': customer_id,
                    'order_id': order_id,
                    'product_id': str(row.product_id),
                    'category': row.category,
                    'product_type': row.product_type,
                    'quantity': int(row.quantity or 0),
                    'price': float(row.price or 0),
                    'refund_amount': float(row.refund_amount or 0)
                }
                customer_items.append(item)

        if not customer_orders:
            logger.warning(f"No orders found for customer {customer_id}")
            return None

        # Step 2: Extract features (e-commerce feature extractor)
        features = self.feature_extractor.extract_all_features(
            customer_id,
            customer_orders,
            customer_items
        )

        # Step 3: Load discovered segments for this store
        if segments_dict is not None:
            # Use provided in-memory segments (for clustering pipeline)
            discovered_segments = segments_dict
        else:
            # Load from database (for normal profiling)
            discovered_segments = await self._load_discovered_segments(store_id)

        # DEBUG: Log axis mismatch for troubleshooting
        feature_axes = set(features.keys())
        segment_axes = set(discovered_segments.keys())
        if feature_axes != segment_axes:
            logger.warning(f"AXIS MISMATCH for customer {customer_id}:")
            logger.warning(f"  Feature axes ({len(feature_axes)}): {sorted(feature_axes)}")
            logger.warning(f"  Segment axes ({len(segment_axes)}): {sorted(segment_axes)}")
            logger.warning(f"  Missing in segments: {feature_axes - segment_axes}")
            logger.warning(f"  Extra in segments: {segment_axes - feature_axes}")

        # Step 4: Calculate fuzzy membership for each axis
        axis_profiles = {}
        dominant_segments = {}
        fuzzy_memberships = {}
        top2_segments = {}
        membership_strength = {}

        for axis_name, axis_features in features.items():
            if axis_name not in discovered_segments:
                logger.warning(f"Skipping axis {axis_name} - not in discovered_segments")
                continue

            segments = discovered_segments[axis_name]

            # Calculate fuzzy membership
            memberships = self._calculate_fuzzy_membership(
                axis_features,
                segments
            )

            # Find dominant segment
            dominant = max(memberships.items(), key=lambda x: x[1])[0]

            # NEW: Calculate top-2 segments with scores (Phase 1: Combined Approach)
            sorted_memberships = sorted(memberships.items(), key=lambda x: x[1], reverse=True)
            top2 = sorted_memberships[:2]  # Top 2 segments

            # NEW: Determine membership strength
            if len(top2) >= 1:
                primary_score = top2[0][1]
                secondary_score = top2[1][1] if len(top2) > 1 else 0.0

                if primary_score > 0.7:
                    strength = "strong"  # Dominant segment very clear
                elif primary_score > 0.4 and secondary_score > 0.3:
                    strength = "balanced"  # Split between top 2
                else:
                    strength = "weak"  # No clear dominant
            else:
                strength = "weak"

            axis_profiles[axis_name] = CustomerAxisProfile(
                customer_id=customer_id,
                axis_name=axis_name,
                memberships=memberships,
                dominant_segment=dominant,
                features=axis_features,
                calculated_at=datetime.now(timezone.utc)
            )

            dominant_segments[axis_name] = dominant
            fuzzy_memberships[axis_name] = memberships
            top2_segments[axis_name] = top2
            membership_strength[axis_name] = strength

        # Step 5: Generate interpretation
        interpretation = self._generate_interpretation(axis_profiles)

        profile = CustomerMultiAxisProfile(
            customer_id=customer_id,
            store_id=store_id,
            axis_profiles=axis_profiles,
            dominant_segments=dominant_segments,
            fuzzy_memberships=fuzzy_memberships,
            top2_segments=top2_segments,
            membership_strength=membership_strength,
            interpretation=interpretation,
            calculated_at=datetime.now(timezone.utc)
        )

        # Step 6: Store profile if requested
        if store_profile:
            await self._store_customer_profile(profile, store_id)

        return profile


    async def _fetch_order_data(
        self,
        store_id: str
    ) -> Dict[str, Any]:
        """
        Fetch order data for all customers from e-commerce platform.

        Returns:
            {
                'customers': [customer_ids],
                'orders': [order dicts],
                'items': [item dicts],
                'customer_orders': {customer_id: [orders]},
                'customer_items': {customer_id: [items]}
            }
        """
        async with get_db_session() if not self.db_session else self._noop_context() as session:
            db = session or self.db_session

            try:
                # Query: Get all orders with items from combined_sales
                # This table has one row per line item, so we aggregate orders and collect items
                query = text("""
                    SELECT
                        customer_id,
                        order_id,
                        order_date,
                        order_total as total_price,
                        line_item_discount as discount_amount,
                        sales_channel as source,
                        product_id,
                        category,
                        product_type,
                        quantity,
                        line_item_sales as price,
                        line_item_refunds as refund_amount
                    FROM combined_sales
                    WHERE customer_id IS NOT NULL
                    ORDER BY customer_id, order_date
                    LIMIT 500000
                """)

                result = await db.execute(query)
                rows = result.fetchall()

                # Organize data
                customers = set()
                orders_dict = {}
                items = []
                customer_orders = defaultdict(list)
                customer_items = defaultdict(list)

                for row in rows:
                    customer_id = str(row.customer_id)
                    order_id = str(row.order_id)

                    customers.add(customer_id)

                    # Add order (avoid duplicates)
                    if order_id not in orders_dict:
                        order = {
                            'customer_id': customer_id,
                            'order_id': order_id,
                            'order_date': row.order_date,
                            'total_price': float(row.total_price or 0),
                            'discount_amount': float(row.discount_amount or 0),
                            'source': row.source
                        }
                        orders_dict[order_id] = order
                        customer_orders[customer_id].append(order)

                    # Add item
                    if row.product_id:
                        item = {
                            'customer_id': customer_id,
                            'order_id': order_id,
                            'product_id': str(row.product_id),
                            'category': row.category,
                            'product_type': row.product_type,
                            'quantity': int(row.quantity or 0),
                            'price': float(row.price or 0),
                            'refund_amount': float(row.refund_amount or 0)
                        }
                        items.append(item)
                        customer_items[customer_id].append(item)

                logger.info(
                    f"Loaded {len(orders_dict)} orders, {len(items)} items "
                    f"from {len(customers)} customers"
                )

                return {
                    'customers': list(customers),
                    'orders': list(orders_dict.values()),
                    'items': items,
                    'customer_orders': dict(customer_orders),
                    'customer_items': dict(customer_items)
                }

            except Exception as e:
                logger.error(f"Failed to fetch order data: {e}", exc_info=True)
                return {
                    'customers': [],
                    'orders': [],
                    'items': [],
                    'customer_orders': {},
                    'customer_items': {}
                }


    async def _fetch_customer_orders(
        self,
        customer_id: str,
        store_id: str
    ) -> Dict[str, Any]:
        """Fetch orders for single customer"""
        async with get_db_session() if not self.db_session else self._noop_context() as session:
            db = session or self.db_session

            try:
                query = text("""
                    SELECT
                        order_id,
                        order_date,
                        order_total as total_price,
                        line_item_discount as discount_amount,
                        sales_channel as source,
                        product_id,
                        category,
                        product_type,
                        quantity,
                        line_item_sales as price,
                        line_item_refunds as refund_amount
                    FROM combined_sales
                    WHERE customer_id = :customer_id
                    ORDER BY order_date
                """)

                result = await db.execute(query, {
                    "customer_id": customer_id
                })
                rows = result.fetchall()

                orders = {}
                items = []

                for row in rows:
                    order_id = str(row.order_id)

                    if order_id not in orders:
                        orders[order_id] = {
                            'order_id': order_id,
                            'order_date': row.order_date,
                            'total_price': float(row.total_price or 0),
                            'discount_amount': float(row.discount_amount or 0),
                            'source': row.source
                        }

                    if row.product_id:
                        items.append({
                            'order_id': order_id,
                            'product_id': str(row.product_id),
                            'category': row.category,
                            'product_type': row.product_type,
                            'quantity': int(row.quantity or 0),
                            'price': float(row.price or 0),
                            'refund_amount': float(row.refund_amount or 0)
                        })

                return {
                    'orders': list(orders.values()),
                    'items': items
                }

            except Exception as e:
                logger.error(f"Failed to fetch orders for {customer_id}: {e}", exc_info=True)
                return {'orders': [], 'items': []}


    def _prepare_axis_matrix(
        self,
        all_customer_features: Dict[str, Dict[str, Dict[str, float]]],
        axis_name: str
    ) -> Tuple[np.ndarray, List[str], List[str]]:
        """
        Convert customer features for one axis into clustering matrix.

        Args:
            all_customer_features: {customer_id: {axis: {feature: value}}}
            axis_name: Which axis to extract (e.g., 'purchase_frequency')

        Returns:
            X: Feature matrix (n_customers × n_features)
            feature_names: List of feature names
            customer_ids: List of customer IDs (matches X row order)
        """
        customers_with_data = []
        feature_dicts = []

        # Collect features for customers who have data for this axis
        for customer_id, axes_features in all_customer_features.items():
            if axis_name in axes_features and axes_features[axis_name]:
                customers_with_data.append(customer_id)
                feature_dicts.append(axes_features[axis_name])

        if not feature_dicts:
            logger.warning(f"No customers with features for axis: {axis_name}")
            return np.array([]), [], []

        # Get feature names (from first customer, assume all have same features)
        feature_names = sorted(feature_dicts[0].keys())

        # Build matrix
        X = np.array([
            [fd.get(fname, 0.0) for fname in feature_names]
            for fd in feature_dicts
        ])

        logger.info(
            f"Prepared matrix for {axis_name}: "
            f"{len(customers_with_data)} customers × {len(feature_names)} features"
        )

        return X, feature_names, customers_with_data


    async def _get_all_event_types(self, store_id: str) -> List[str]:
        """Get all event types for this store"""
        async with get_db_session() if not self.db_session else self._noop_context() as session:
            db = session or self.db_session

            try:
                query = text("""
                    SELECT DISTINCT event_type
                    FROM customer_behavior_events
                    WHERE store_id = :store_id
                """)

                result = await db.execute(query, {"store_id": store_id})
                rows = result.fetchall()

                return [row.event_type for row in rows]

            except Exception as e:
                logger.error(f"Failed to fetch event types: {e}", exc_info=True)
                return []


    async def _extract_all_customer_features(
        self,
        event_data: Dict[str, Any],
        all_event_types: List[str],
        store_launch_date: Optional[datetime]
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Extract features for all customers across all axes.

        Returns:
            {customer_id: {axis_name: {feature_name: value}}}
        """
        customer_features = {}

        for customer_id, customer_events in event_data['customer_events'].items():
            try:
                features = self.feature_extractor.extract_all_features(
                    customer_events,
                    all_event_types,
                    store_launch_date
                )
                customer_features[customer_id] = features

            except Exception as e:
                logger.error(
                    f"Failed to extract features for customer {customer_id}: {e}",
                    exc_info=True
                )

        return customer_features


    async def _cluster_axis(
        self,
        axis_name: str,
        customer_features: Dict[str, Dict[str, Dict[str, float]]],
        store_id: str
    ) -> List[DiscoveredSegment]:
        """
        Cluster customers on one axis.

        Returns list of discovered segments for this axis.
        """
        # Step 1: Extract features for this axis from all customers
        X_dict = {}
        customer_ids = []

        for customer_id, all_features in customer_features.items():
            if axis_name not in all_features:
                continue

            axis_features = all_features[axis_name]
            if not axis_features:
                continue

            X_dict[customer_id] = axis_features
            customer_ids.append(customer_id)

        if len(customer_ids) < self.min_population:
            logger.warning(
                f"Insufficient customers with {axis_name} features: {len(customer_ids)}"
            )
            return []

        # Step 2: Convert to matrix
        feature_names = list(next(iter(X_dict.values())).keys())
        X = np.array([[X_dict[pid][fname] for fname in feature_names] for pid in customer_ids])

        # Handle NaN/inf
        X = np.nan_to_num(X, nan=0.0, posinf=1e10, neginf=-1e10)

        # Step 3: Normalize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Step 4: Find optimal k
        optimal_k, silhouette = self._find_optimal_k(X_scaled, axis_name)

        if optimal_k < 2 or silhouette < self.min_silhouette:
            logger.warning(
                f"Poor clustering quality for {axis_name}: "
                f"k={optimal_k}, silhouette={silhouette:.3f}"
            )
            # Still create clusters but log warning
            optimal_k = max(optimal_k, 2)

        logger.info(
            f"{axis_name}: optimal k={optimal_k}, silhouette={silhouette:.3f}"
        )

        # Step 5: Cluster
        kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        # Step 6: Extract scaler parameters for fuzzy membership calculation
        # CRITICAL FIX: Store population scaler params so inference uses same standardization
        scaler_params = {
            'mean': scaler.mean_.tolist(),
            'scale': scaler.scale_.tolist(),
            'feature_names': feature_names  # Ensure feature order is preserved
        }

        # Step 7: Create segments
        segments = []
        for cluster_id in range(optimal_k):
            cluster_mask = labels == cluster_id
            cluster_customer_ids = [customer_ids[i] for i, m in enumerate(cluster_mask) if m]

            # Interpret cluster
            cluster_center_scaled = kmeans.cluster_centers_[cluster_id]
            cluster_center_original = scaler.inverse_transform(
                cluster_center_scaled.reshape(1, -1)
            )[0]

            segment_name, interpretation = await self._interpret_cluster(
                axis_name,
                cluster_center_original,
                feature_names,
                X  # Pass population data for AI naming
            )

            segment = DiscoveredSegment(
                segment_id=f"{store_id}_{axis_name}_{segment_name}",
                axis_name=axis_name,
                segment_name=segment_name,
                cluster_center=cluster_center_scaled,  # Store scaled for membership calc
                feature_names=feature_names,
                scaler_params=scaler_params,  # FIX: Store population scaler
                population_percentage=len(cluster_customer_ids) / len(customer_ids),
                customer_count=len(cluster_customer_ids),
                interpretation=interpretation
            )

            segments.append(segment)

        return segments


    def _find_optimal_k(
        self,
        X: np.ndarray,
        axis_name: str
    ) -> Tuple[int, float]:
        """
        Find optimal number of clusters using silhouette score.

        Returns (optimal_k, best_silhouette)
        """
        best_k = 2
        best_silhouette = -1

        for k in range(self.min_k, min(self.max_k + 1, len(X))):
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = kmeans.fit_predict(X)

                silhouette = silhouette_score(X, labels)

                if silhouette > best_silhouette:
                    best_silhouette = silhouette
                    best_k = k

            except Exception as e:
                logger.warning(f"Failed to try k={k} for {axis_name}: {e}")

        return best_k, best_silhouette


    async def _interpret_cluster(
        self,
        axis_name: str,
        cluster_center: np.ndarray,
        feature_names: List[str],
        population_X: np.ndarray
    ) -> Tuple[str, str]:
        """
        Interpret cluster by examining centroid features.
        Uses AI naming if enabled, otherwise falls back to generic naming.

        Returns (segment_name, interpretation)
        """
        # Use AI naming if enabled and API key available
        if self.use_ai_naming and self.anthropic_api_key:
            try:
                segment_name, interpretation = await name_segment_with_ai(
                    axis_name=axis_name,
                    cluster_center=cluster_center,
                    feature_names=feature_names,
                    population_X=population_X,
                    anthropic_api_key=self.anthropic_api_key
                )
                return segment_name, interpretation
            except Exception as e:
                logger.warning(f"AI naming failed for {axis_name}, using fallback: {e}")

        # Fallback: Create generic naming based on feature values
        features = {name: cluster_center[i] for i, name in enumerate(feature_names)}
        sorted_features = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)
        top_feature = sorted_features[0][0] if sorted_features else "unknown"

        segment_name = f"{axis_name}_{top_feature}"
        interpretation = f"Cluster characterized by {top_feature}"

        return segment_name, interpretation


    def _interpret_temporal_cluster(self, features, top_features):
        """Interpret temporal pattern cluster"""
        weekend_ratio = features.get('weekend_ratio', 0)
        session_length = features.get('avg_session_length_min', 0)

        if weekend_ratio > 0.6:
            name = "weekend_warrior"
            desc = f"Plays primarily on weekends ({weekend_ratio*100:.0f}% weekend)"
        elif session_length > 180:
            name = "binge_customer"
            desc = f"Long play sessions (avg {session_length:.0f} minutes)"
        elif features.get('play_frequency', 0) > 0.8:
            name = "consistent_daily"
            desc = f"Plays daily ({features.get('play_frequency', 0)*100:.0f}% of days)"
        else:
            name = "weekday_regular"
            desc = "Regular weekday customer"

        return name, desc


    def _interpret_intensity_cluster(self, features, top_features):
        """Interpret intensity pattern cluster"""
        events_per_day = features.get('events_per_day', 0)
        intensity_trend = features.get('intensity_trend', 0)

        if events_per_day > 50:
            name = "hardcore"
            desc = f"Very high intensity ({events_per_day:.0f} events/day)"
        elif events_per_day < 10:
            if intensity_trend < -1:
                name = "declining"
                desc = "Low intensity and declining (churn risk)"
            else:
                name = "casual"
                desc = f"Low intensity ({events_per_day:.0f} events/day)"
        else:
            name = "moderate"
            desc = f"Moderate intensity ({events_per_day:.0f} events/day)"

        return name, desc


    def _interpret_progression_cluster(self, features, top_features):
        """Interpret progression velocity cluster"""
        repeat_ratio = features.get('repeat_event_ratio', 0)
        diversity = features.get('event_type_coverage', 0)

        if diversity > 0.8 and repeat_ratio < 0.3:
            name = "completionist"
            desc = f"High diversity ({diversity*100:.0f}% coverage), exploring everything"
        elif repeat_ratio > 0.7:
            name = "grinder"
            desc = f"Focused repetition ({repeat_ratio*100:.0f}% on favorite events)"
        elif diversity > 0.6:
            name = "explorer"
            desc = f"High exploration ({diversity*100:.0f}% event coverage)"
        else:
            name = "rusher"
            desc = "Low diversity, focused progression"

        return name, desc


    def _interpret_content_cluster(self, features, top_features):
        """Interpret content consumption cluster"""
        coverage = features.get('content_coverage', 0)
        velocity = features.get('content_coverage_velocity', 0)

        if coverage > 0.7 and velocity > 0.02:
            name = "content_locust"
            desc = f"Fast consumption ({coverage*100:.0f}% coverage, high velocity)"
        elif features.get('depth_focus', 0) > 0.6:
            name = "depth_focused"
            desc = "Deep engagement with favorite content"
        elif coverage < 0.3:
            name = "sampler"
            desc = "Low coverage, trying different content"
        else:
            name = "steady_consumer"
            desc = "Steady content consumption pace"

        return name, desc


    def _interpret_learning_cluster(self, features, top_features):
        """Interpret learning curve cluster"""
        diversity_growth = features.get('diversity_growth', 0)
        learning_efficiency = features.get('learning_efficiency', 0)

        if diversity_growth > 5 and learning_efficiency > 0.3:
            name = "fast_learner"
            desc = "Rapid feature adoption and mastery"
        elif diversity_growth < 2:
            name = "struggling"
            desc = "Slow feature discovery (may need help)"
        elif features.get('early_diversity', 0) > features.get('late_diversity', 0):
            name = "tutorial_skipper"
            desc = "Skipped tutorials, explored early"
        else:
            name = "steady_learner"
            desc = "Gradual, consistent learning"

        return name, desc


    def _interpret_volatility_cluster(self, features, top_features):
        """Interpret volatility/stability cluster"""
        predictability = features.get('predictability_score', 0)
        stability = features.get('event_distribution_stability', 0)

        if predictability > 0.7 and stability > 0.7:
            name = "routine_user"
            desc = "Highly consistent, predictable behavior"
        elif predictability < 0.3:
            name = "variable_user"
            desc = "Unpredictable, variable behavior"
        elif features.get('event_distribution_volatility', 0) > 1.0:
            name = "exploratory"
            desc = "Constantly trying new things"
        else:
            name = "habit_breaking"
            desc = "Changing behavior patterns"

        return name, desc


    def _interpret_purchase_cluster(self, features, top_features):
        """Interpret purchase timing cluster"""
        days_after = features.get('days_after_launch', 0)

        if days_after <= 7:
            name = "launch_buyer"
            desc = f"Purchased at launch ({days_after:.0f} days)"
        elif days_after <= 90:
            name = "early_adopter"
            desc = f"Early adopter ({days_after:.0f} days after launch)"
        elif days_after <= 180:
            name = "patient_storer"
            desc = f"Patient storer ({days_after:.0f} days after launch)"
        else:
            name = "late_adopter"
            desc = f"Late adopter ({days_after:.0f} days after launch)"

        return name, desc


    def _calculate_fuzzy_membership(
        self,
        customer_features: Dict[str, float],
        segments: List[DiscoveredSegment]
    ) -> Dict[str, float]:
        """
        Calculate fuzzy membership for customer across all segments in axis.

        CRITICAL FIX: Uses population scaler from training to standardize customer features,
        ensuring they're in the same coordinate space as cluster centers.

        Uses inverse distance weighting:
        - Close to cluster center = high membership
        - Far from cluster center = low membership
        - Memberships sum to 1.0

        Returns:
            {segment_name: membership_strength}
        """
        # Convert customer features to vector
        feature_names = segments[0].feature_names
        customer_vector = np.array([customer_features.get(fname, 0) for fname in feature_names])

        # Handle NaN/inf
        customer_vector = np.nan_to_num(customer_vector, nan=0.0, posinf=1e10, neginf=-1e10)

        # CRITICAL FIX: Use POPULATION scaler from training, not customer's own statistics
        # All segments in an axis share the same scaler params
        scaler_params = segments[0].scaler_params
        mean = np.array(scaler_params['mean'])
        scale = np.array(scaler_params['scale'])

        # Standardize using population statistics (same as training)
        customer_vector_scaled = (customer_vector - mean) / scale

        # Calculate distances to all cluster centers
        distances = []
        for segment in segments:
            dist = np.linalg.norm(customer_vector_scaled - segment.cluster_center)
            distances.append(dist)

        # Convert distances to similarities (inverse)
        # Use softmax-like approach for smooth membership
        distances = np.array(distances)
        similarities = np.exp(-distances)  # Exponential decay

        # Normalize to sum to 1.0
        total = np.sum(similarities)
        memberships = similarities / total if total > 0 else np.ones(len(segments)) / len(segments)

        return {
            segments[i].segment_name: float(memberships[i])
            for i in range(len(segments))
        }


    def _generate_interpretation(
        self,
        axis_profiles: Dict[str, CustomerAxisProfile]
    ) -> str:
        """Generate human-readable interpretation from axis profiles"""
        parts = []

        # Collect dominant segments
        if 'temporal_patterns' in axis_profiles:
            parts.append(axis_profiles['temporal_patterns'].dominant_segment.replace('_', ' ').title())

        if 'progression_velocity' in axis_profiles:
            parts.append(axis_profiles['progression_velocity'].dominant_segment.replace('_', ' ').lower())

        if 'intensity_patterns' in axis_profiles:
            intensity = axis_profiles['intensity_patterns'].dominant_segment
            parts.append(f"with {intensity} intensity")

        # Add special notes
        notes = []

        if 'content_consumption' in axis_profiles:
            if axis_profiles['content_consumption'].dominant_segment == 'content_locust':
                notes.append("consuming content rapidly (exhaustion risk)")

        if 'intensity_patterns' in axis_profiles:
            if axis_profiles['intensity_patterns'].dominant_segment == 'declining':
                notes.append("showing declining engagement (churn risk)")

        if 'learning_curve' in axis_profiles:
            learning = axis_profiles['learning_curve'].dominant_segment
            if learning == 'fast_learner':
                notes.append("mastered quickly")
            elif learning == 'struggling':
                notes.append("may need assistance")

        # Combine
        interpretation = ' '.join(parts)
        if notes:
            interpretation += '. ' + ', '.join(notes).capitalize()

        return interpretation


    async def _store_discovered_segments(
        self,
        store_id: str,
        discovered_segments: Dict[str, List[DiscoveredSegment]]
    ):
        """Store discovered segments in database"""
        if not discovered_segments:
            logger.warning("No segments to store")
            return

        # Use existing session or create new one
        if self.db_session:
            async with self._noop_context():
                await self._store_segments_impl(self.db_session, store_id, discovered_segments)
        else:
            async with get_db_session() as session:
                await self._store_segments_impl(session, store_id, discovered_segments)

    async def _store_segments_impl(self, session, store_id, discovered_segments):
        """Implementation of segment storage"""
        try:
            # Delete existing segments for this store (replace strategy)
            await session.execute(
                text("DELETE FROM multi_axis_segments WHERE store_id = :store_id"),
                {"store_id": store_id}
            )

            # Insert new segments
            for axis_name, segments in discovered_segments.items():
                for idx, segment in enumerate(segments):
                    # Convert numpy array to list for JSON storage
                    cluster_center_list = segment.cluster_center.tolist()

                    # Always append index to segment name to ensure uniqueness within axis
                    # (interpretation may generate duplicate names)
                    segment_name = f"{segment.segment_name}_{idx}"

                    await session.execute(
                        text("""
                            INSERT INTO multi_axis_segments (
                                segment_id, store_id, axis_name, segment_name,
                                cluster_center, feature_names, scaler_params, population_percentage,
                                customer_count, interpretation, created_at, updated_at
                            ) VALUES (
                                :segment_id, :store_id, :axis_name, :segment_name,
                                :cluster_center, :feature_names, :scaler_params, :population_percentage,
                                :customer_count, :interpretation, NOW(), NOW()
                            )
                        """),
                        {
                            "segment_id": str(uuid.uuid4()),
                            "store_id": store_id,
                            "axis_name": axis_name,
                            "segment_name": segment_name,
                            "cluster_center": json.dumps(cluster_center_list),
                            "feature_names": json.dumps(segment.feature_names),
                            "scaler_params": json.dumps(segment.scaler_params),  # FIX: Store scaler params
                            "population_percentage": segment.population_percentage,
                            "customer_count": segment.customer_count,
                            "interpretation": segment.interpretation
                        }
                    )

            # Commit within the transaction
            await session.flush()

            total_segments = sum(len(segs) for segs in discovered_segments.values())
            logger.info(
                f"Stored {total_segments} segments across {len(discovered_segments)} axes "
                f"for store {store_id}"
            )

        except Exception as e:
            logger.error(f"Error storing segments: {e}")
            raise


    async def _load_discovered_segments(
        self,
        store_id: str
    ) -> Dict[str, List[DiscoveredSegment]]:
        """Load discovered segments from database"""
        # Use existing session or create new one
        if self.db_session:
            async with self._noop_context():
                return await self._load_segments_impl(self.db_session, store_id)
        else:
            async with get_db_session() as session:
                return await self._load_segments_impl(session, store_id)

    async def _load_segments_impl(self, session, store_id):
        """Implementation of segment loading"""
        try:
            result = await session.execute(
                text("""
                    SELECT
                        segment_id, axis_name, segment_name, cluster_center,
                        feature_names, scaler_params, population_percentage, customer_count, interpretation
                    FROM multi_axis_segments
                    WHERE store_id = :store_id
                    ORDER BY axis_name, segment_name
                """),
                {"store_id": store_id}
            )

            rows = result.fetchall()

            if not rows:
                logger.info(f"No segments found for store {store_id}")
                return {}

            # Group segments by axis
            discovered_segments: Dict[str, List[DiscoveredSegment]] = defaultdict(list)

            for row in rows:
                # Parse JSON data (JSONB columns are already parsed by PostgreSQL)
                cluster_center_data = row[3]
                if isinstance(cluster_center_data, str):
                    cluster_center = np.array(json.loads(cluster_center_data))
                else:
                    cluster_center = np.array(cluster_center_data)

                feature_names_data = row[4]
                if isinstance(feature_names_data, str):
                    feature_names = json.loads(feature_names_data)
                else:
                    feature_names = feature_names_data

                # FIX: Load scaler_params for correct fuzzy membership
                scaler_params_data = row[5]
                if scaler_params_data is None:
                    # Legacy segments without scaler_params - will cause errors
                    logger.warning(
                        f"Segment {row[0]} has no scaler_params - rediscovery required for accurate memberships"
                    )
                    # Skip this segment or use dummy scaler
                    continue

                if isinstance(scaler_params_data, str):
                    scaler_params = json.loads(scaler_params_data)
                else:
                    scaler_params = scaler_params_data

                segment = DiscoveredSegment(
                    segment_id=row[0],
                    axis_name=row[1],
                    segment_name=row[2],
                    cluster_center=cluster_center,
                    feature_names=feature_names,
                    scaler_params=scaler_params,  # FIX: Load scaler params
                    population_percentage=row[6],
                    customer_count=row[7],
                    interpretation=row[8]
                )

                discovered_segments[row[1]].append(segment)

            logger.info(
                f"Loaded {len(rows)} segments across {len(discovered_segments)} axes "
                f"for store {store_id}"
            )

            return dict(discovered_segments)

        except Exception as e:
            logger.error(f"Error loading segments: {e}")
            raise


    async def _store_customer_profile(
        self,
        profile: CustomerMultiAxisProfile,
        store_id: str
    ):
        """Store customer's fuzzy membership profile in database"""
        if not profile or not profile.axis_profiles:
            logger.warning("No profile to store")
            return

        # Use existing session or create new one
        if self.db_session:
            async with self._noop_context():
                await self._store_profile_impl(self.db_session, profile, store_id)
        else:
            async with get_db_session() as session:
                await self._store_profile_impl(session, profile, store_id)

    async def _store_profile_impl(self, session, profile, store_id):
        """Implementation of profile storage"""
        try:
            # Delete existing memberships for this customer (replace strategy)
            await session.execute(
                text("""
                    DELETE FROM customer_axis_memberships
                    WHERE customer_id = :customer_id AND store_id = :store_id
                """),
                {"customer_id": profile.customer_id, "store_id": store_id}
            )

            # Insert new memberships for each axis
            for axis_name, axis_profile in profile.axis_profiles.items():
                await session.execute(
                    text("""
                        INSERT INTO customer_axis_memberships (
                            membership_id, customer_id, store_id, axis_name,
                            memberships, dominant_segment, features, calculated_at
                        ) VALUES (
                            :membership_id, :customer_id, :store_id, :axis_name,
                            :memberships, :dominant_segment, :features, :calculated_at
                        )
                    """),
                    {
                        "membership_id": str(uuid.uuid4()),
                        "customer_id": profile.customer_id,
                        "store_id": store_id,
                        "axis_name": axis_name,
                        "memberships": json.dumps(axis_profile.memberships),
                        "dominant_segment": axis_profile.dominant_segment,
                        "features": json.dumps(axis_profile.features),
                        "calculated_at": axis_profile.calculated_at
                    }
                )

            await session.flush()

            logger.info(
                f"Stored profile for customer {profile.customer_id} across "
                f"{len(profile.axis_profiles)} axes"
            )

        except Exception as e:
            logger.error(f"Error storing customer profile: {e}")
            raise


    async def _log_discovery_run(
        self,
        run_id: str,
        store_id: str,
        customer_count: int,
        event_count: int,
        axes_discovered: int,
        total_segments: int,
        avg_silhouette_score: float,
        started_at: datetime,
        status: str,
        error_message: Optional[str] = None,
        processing_time_seconds: Optional[float] = None
    ):
        """Log discovery run metadata for auditing and performance tracking"""
        # Use existing session or create new one
        if self.db_session:
            async with self._noop_context():
                await self._log_run_impl(
                    self.db_session, run_id, store_id, customer_count, event_count,
                    axes_discovered, total_segments, avg_silhouette_score,
                    started_at, status, error_message, processing_time_seconds
                )
        else:
            async with get_db_session() as session:
                await self._log_run_impl(
                    session, run_id, store_id, customer_count, event_count,
                    axes_discovered, total_segments, avg_silhouette_score,
                    started_at, status, error_message, processing_time_seconds
                )

    async def _log_run_impl(
        self, session, run_id, store_id, customer_count, event_count,
        axes_discovered, total_segments, avg_silhouette_score,
        started_at, status, error_message, processing_time_seconds
    ):
        """Implementation of discovery run logging"""
        try:
            completed_at = datetime.now(timezone.utc)

            if processing_time_seconds is None:
                processing_time_seconds = (completed_at - started_at).total_seconds()

            await session.execute(
                text("""
                    INSERT INTO multi_axis_discovery_runs (
                        run_id, store_id, customer_count, event_count,
                        axes_discovered, total_segments, avg_silhouette_score,
                        discovery_started_at, discovery_completed_at,
                        processing_time_seconds, status, error_message
                    ) VALUES (
                        :run_id, :store_id, :customer_count, :event_count,
                        :axes_discovered, :total_segments, :avg_silhouette_score,
                        :discovery_started_at, :discovery_completed_at,
                        :processing_time_seconds, :status, :error_message
                    )
                """),
                {
                    "run_id": run_id,
                    "store_id": store_id,
                    "customer_count": customer_count,
                    "event_count": event_count,
                    "axes_discovered": axes_discovered,
                    "total_segments": total_segments,
                    "avg_silhouette_score": avg_silhouette_score,
                    "discovery_started_at": started_at,
                    "discovery_completed_at": completed_at,
                    "processing_time_seconds": processing_time_seconds,
                    "status": status,
                    "error_message": error_message
                }
            )

            await session.flush()

            logger.info(f"Logged discovery run {run_id} (status: {status})")

        except Exception as e:
            logger.error(f"Error logging discovery run: {e}")
            # Don't raise - logging failure shouldn't break discovery


    def _noop_context(self):
        """No-op context manager when session already provided"""
        class NoopContext:
            async def __aenter__(self):
                return None
            async def __aexit__(self, *args):
                pass
        return NoopContext()
