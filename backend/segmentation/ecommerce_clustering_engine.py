"""
E-Commerce Multi-Axis Clustering Engine

Discovers behavioral segments by clustering customers independently across
multiple behavioral dimensions (axes). Uses fuzzy membership so customers
belong to ALL segments with varying strengths (0.0-1.0).

Adapted from gaming industry multi-axis clustering for e-commerce order data.

Core Algorithm:
1. Extract features for all customers across all axes (order history)
2. For each axis independently:
   - Normalize features (StandardScaler with population statistics)
   - Find optimal k (number of clusters) using silhouette score
   - Cluster customers using KMeans
   - Calculate fuzzy membership (exponential decay from distances)
   - Generate AI-powered segment names (via Claude API)
3. Store discovered segments and customer memberships in PostgreSQL

Author: Quimbi Platform (E-Commerce Adaptation)
Version: 4.0.0 (E-Commerce)
Date: November 6, 2025
"""

import numpy as np
import logging
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import uuid
import json

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import silhouette_score

from backend.core.database import get_db_session
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSegment:
    """A segment discovered within an axis"""
    segment_id: str
    axis_name: str
    segment_name: str  # AI-generated name
    cluster_center: np.ndarray  # In scaled space
    feature_names: List[str]
    scaler_params: Dict[str, List[float]]  # Population scaler: {"mean": [...], "scale": [...]}
    population_percentage: float
    customer_count: int
    interpretation: str  # AI-generated interpretation
    fuzzy_membership_matrix: Optional[np.ndarray] = None  # (n_customers, k) if FCM enabled
    customer_fuzzy_scores: Optional[Dict[str, float]] = None  # {customer_id: membership_score}


@dataclass
class CustomerAxisProfile:
    """Customer's fuzzy membership profile for one axis"""
    customer_id: str
    axis_name: str
    memberships: Dict[str, float]  # {segment_name: membership_strength (0-1)}
    dominant_segment: str  # Segment with highest membership
    features: Dict[str, float]  # Raw feature values
    calculated_at: datetime


@dataclass
class CustomerMultiAxisProfile:
    """Customer's complete behavioral profile across all axes"""
    customer_id: str
    store_id: str
    axis_profiles: Dict[str, CustomerAxisProfile]  # {axis_name: profile}
    dominant_segments: Dict[str, str]  # {axis_name: segment_name}

    # Fuzzy membership tracking
    fuzzy_memberships: Dict[str, Dict[str, float]] = field(default_factory=dict)  # {axis: {segment: score}}
    top2_segments: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)  # {axis: [(seg1, score1), (seg2, score2)]}
    membership_strength: Dict[str, str] = field(default_factory=dict)  # {axis: "strong"|"balanced"|"weak"}

    interpretation: str = ""
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EcommerceClusteringEngine:
    """
    Discovers behavioral segments across multiple independent axes for e-commerce.

    Supports 14 axes:
    - 8 marketing-focused (purchase patterns, value, categories, etc.)
    - 6 support-focused (communication, problems, loyalty, expertise, etc.)

    Each axis is clustered separately to find natural behavioral patterns.
    Customers get fuzzy membership in all segments per axis.
    """

    def __init__(
        self,
        db_session=None,
        # Clustering parameters
        min_k: int = 2,
        max_k: int = 6,
        min_silhouette: float = 0.3,
        min_population: int = 100,
        # AI naming
        use_ai_naming: bool = True,
        anthropic_api_key: Optional[str] = None,
        # Enhanced clustering features (feature-flagged)
        enable_dynamic_k: Optional[bool] = None,
        enable_robust_scaling: Optional[bool] = None,
        winsorize_percentile: float = 99.0,
        max_dominant_segment_pct: float = 50.0,
        min_segment_size_pct: float = 3.0,
        # Fuzzy C-Means (FCM) - for temporal thumbprint tracking
        use_fuzzy_cmeans: Optional[bool] = None,
        fuzzy_m: float = 2.0
    ):
        """
        Initialize e-commerce clustering engine.

        Args:
            db_session: Database session (optional)
            min_k: Minimum clusters per axis (default: 2)
            max_k: Maximum clusters per axis (default: 6)
            min_silhouette: Minimum acceptable silhouette score (default: 0.3)
            min_population: Minimum customers required for discovery (default: 100)
            use_ai_naming: Use Claude API for segment naming (default: True)
            anthropic_api_key: Anthropic API key for AI naming
            enable_dynamic_k: Enable dynamic k-range optimization (default: from env)
            enable_robust_scaling: Enable robust outlier handling (default: from env)
            winsorize_percentile: Percentile for outlier capping (default: 99.0)
            max_dominant_segment_pct: Max % in largest segment (default: 50%)
            min_segment_size_pct: Min % per segment (default: 3%)
            use_fuzzy_cmeans: Use Fuzzy C-Means instead of K-Means (default: from env)
            fuzzy_m: Fuzziness parameter for FCM, 1.5-3.0 (default: 2.0)
        """
        self.db_session = db_session

        # Clustering parameters
        self.min_k = min_k
        self.max_k = max_k
        self.min_silhouette = min_silhouette
        self.min_population = min_population

        # AI naming
        self.use_ai_naming = use_ai_naming
        self.anthropic_api_key = anthropic_api_key

        # Enhanced clustering features (from env or args)
        self.enable_dynamic_k = (
            enable_dynamic_k if enable_dynamic_k is not None
            else os.getenv("ENABLE_DYNAMIC_K_RANGE", "false").lower() == "true"
        )
        self.enable_robust_scaling = (
            enable_robust_scaling if enable_robust_scaling is not None
            else os.getenv("CLUSTERING_ROBUST_SCALING", "true").lower() == "true"
        )
        self.winsorize_percentile = winsorize_percentile
        self.max_dominant_segment_pct = max_dominant_segment_pct
        self.min_segment_size_pct = min_segment_size_pct

        # Initialize dynamic K optimizer if enabled
        self.dynamic_k_optimizer = None
        if self.enable_dynamic_k:
            from backend.segmentation.dynamic_k_optimizer import DynamicKOptimizer, DynamicKOptimizerConfig
            config = DynamicKOptimizerConfig(
                enabled=True,
                min_k=self.min_k,
                max_k=self.max_k,
                min_samples_per_cluster=50,
                silhouette_threshold=self.min_silhouette
            )
            self.dynamic_k_optimizer = DynamicKOptimizer(config)
            logger.info("✅ Dynamic K Optimization ENABLED")

        if self.enable_robust_scaling:
            logger.info("✅ Robust Outlier Handling ENABLED")

        # Fuzzy C-Means (for temporal thumbprint tracking)
        self.use_fuzzy_cmeans = (
            use_fuzzy_cmeans if use_fuzzy_cmeans is not None
            else os.getenv("ENABLE_FUZZY_CMEANS", "false").lower() == "true"
        )
        self.fuzzy_m = fuzzy_m

        if self.use_fuzzy_cmeans:
            logger.info(f"✅ Fuzzy C-Means ENABLED (m={self.fuzzy_m})")

        # Feature extractor will be imported separately
        self.feature_extractor = None


    async def discover_multi_axis_segments(
        self,
        store_id: str,
        axes_to_cluster: Optional[List[str]] = None,
        max_customers: Optional[int] = None
    ) -> Dict[str, List[DiscoveredSegment]]:
        """
        Main entry point: Discover segments across all axes.

        Args:
            store_id: Store identifier (e.g., 'linda_quilting')
            axes_to_cluster: List of axis names (None = all 14 axes)

        Returns:
            Dict mapping axis name to list of discovered segments
        """
        logger.info(f"Starting multi-axis segmentation for store {store_id}")

        # Default: cluster all 14 axes
        if axes_to_cluster is None:
            axes_to_cluster = [
                # Marketing axes (1-8)
                'purchase_frequency',
                'purchase_value',
                'category_exploration',
                'price_sensitivity',
                'purchase_cadence',
                'customer_maturity',
                'repurchase_behavior',
                'return_behavior',
                # Support axes (9-13, excluding 14 which needs Gorgias)
                'communication_preference',
                'problem_complexity_profile',
                'loyalty_trajectory',
                'product_knowledge',
                'value_sophistication'
            ]

        # Step 1: Fetch order data
        order_data = await self._fetch_order_data(store_id, max_customers)

        if len(order_data['customers']) < self.min_population:
            logger.warning(
                f"Insufficient population ({len(order_data['customers'])} customers)"
            )
            return {}

        logger.info(
            f"Loaded {len(order_data['orders'])} orders from "
            f"{len(order_data['customers'])} customers"
        )

        # Step 2: Extract features for all customers across all axes
        customer_features = await self._extract_all_customer_features(
            order_data,
            axes_to_cluster
        )

        logger.info(f"Extracted features for {len(customer_features)} customers")

        # Step 3: Cluster each axis independently
        discovered_segments = {}

        for axis_name in axes_to_cluster:
            logger.info(f"Clustering axis: {axis_name}")

            segments = await self._cluster_axis(
                axis_name,
                customer_features,
                store_id
            )

            if segments:
                discovered_segments[axis_name] = segments
                logger.info(
                    f"Discovered {len(segments)} segments for {axis_name}"
                )
            else:
                logger.warning(f"No segments discovered for {axis_name}")

        # Step 4: Store discovered segments
        await self._store_discovered_segments(store_id, discovered_segments)

        logger.info(
            f"Multi-axis discovery complete: {len(discovered_segments)} axes, "
            f"{sum(len(segs) for segs in discovered_segments.values())} total segments"
        )

        return discovered_segments


    async def calculate_customer_profile(
        self,
        customer_id: str,
        store_id: str,
        store_profile: bool = True
    ) -> CustomerMultiAxisProfile:
        """
        Calculate individual customer's fuzzy membership profile across all axes.

        Args:
            customer_id: Customer identifier
            store_id: Store identifier
            store_profile: If True, save profile to database

        Returns:
            CustomerMultiAxisProfile with fuzzy memberships
        """
        logger.info(f"Calculating profile for customer {customer_id}")

        # Step 1: Get customer's orders
        order_data = await self._fetch_customer_orders(customer_id, store_id)

        if not order_data['orders']:
            logger.warning(f"No orders found for customer {customer_id}")
            return None

        # Step 2: Extract features
        from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor

        feature_extractor = EcommerceFeatureExtractor()
        features = feature_extractor.extract_all_features(
            customer_id,
            order_data['orders'],
            order_data['items']
        )

        # Step 3: Load discovered segments for this store
        discovered_segments = await self._load_discovered_segments(store_id)

        # Step 4: Calculate fuzzy membership for each axis
        axis_profiles = {}
        dominant_segments = {}
        fuzzy_memberships = {}
        top2_segments = {}
        membership_strength = {}

        for axis_name, axis_features in features.items():
            if axis_name not in discovered_segments:
                continue

            segments = discovered_segments[axis_name]

            # Calculate fuzzy membership
            memberships = self._calculate_fuzzy_membership(
                axis_features,
                segments
            )

            # Find dominant segment
            dominant = max(memberships.items(), key=lambda x: x[1])[0]

            # Calculate top-2 segments with scores
            sorted_memberships = sorted(memberships.items(), key=lambda x: x[1], reverse=True)
            top2 = sorted_memberships[:2]

            # Determine membership strength
            if len(top2) >= 1:
                primary_score = top2[0][1]
                secondary_score = top2[1][1] if len(top2) > 1 else 0.0

                if primary_score > 0.7:
                    strength = "strong"
                elif primary_score > 0.4 and secondary_score > 0.3:
                    strength = "balanced"
                else:
                    strength = "weak"
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
        store_id: str,
        max_customers: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch order data for all customers.

        Returns:
            {
                'customers': [customer_ids],
                'orders': [order dicts],
                'items': [item dicts],
                'customer_orders': {customer_id: [orders]}
            }
        """
        async with get_db_session() if not self.db_session else self._noop_context() as session:
            db = session or self.db_session

            try:
                # Query: Get all orders with items from combined_sales
                # NOTE: This uses public.combined_sales (Shopify sync data)
                query = text("""
                    SELECT
                        customer_id,
                        order_id,
                        order_date,
                        line_item_sales as total_price,
                        line_item_discount as discount_amount,
                        sales_channel as source,
                        product_id,
                        category,
                        product_type,
                        quantity,
                        line_item_sales as price,
                        line_item_refunds as refund_amount
                    FROM public.combined_sales
                    WHERE customer_id IS NOT NULL
                    ORDER BY customer_id, order_date
                    LIMIT 500000
                """)

                # If max_customers specified, sample random customers
                if max_customers:
                    query = text(f"""
                        WITH sampled_customers AS (
                            SELECT customer_id
                            FROM (
                                SELECT DISTINCT customer_id
                                FROM public.combined_sales
                                WHERE customer_id IS NOT NULL
                            ) unique_customers
                            ORDER BY RANDOM()
                            LIMIT {max_customers}
                        )
                        SELECT
                            cs.customer_id,
                            cs.order_id,
                            cs.order_date,
                            cs.line_item_sales as total_price,
                            cs.line_item_discount as discount_amount,
                            cs.sales_channel as source,
                            cs.product_id,
                            cs.category,
                            cs.product_type,
                            cs.quantity,
                            cs.line_item_sales as price,
                            cs.line_item_refunds as refund_amount
                        FROM public.combined_sales cs
                        INNER JOIN sampled_customers sc ON cs.customer_id = sc.customer_id
                        WHERE cs.customer_id IS NOT NULL
                        ORDER BY cs.customer_id, cs.order_date
                    """)

                result = await db.execute(query)
                rows = result.fetchall()

                # Organize data
                customers = set()
                orders_dict = {}
                items = []
                customer_orders = defaultdict(list)

                for row in rows:
                    customer_id = str(row.customer_id)
                    order_id = str(row.order_id)

                    customers.add(customer_id)

                    # Add order (avoid duplicates)
                    if order_id not in orders_dict:
                        orders_dict[order_id] = {
                            'customer_id': customer_id,
                            'order_id': order_id,
                            'order_date': row.order_date,
                            'total_price': float(row.total_price or 0),
                            'discount_amount': float(row.discount_amount or 0),
                            'source': row.source
                        }
                        customer_orders[customer_id].append(orders_dict[order_id])

                    # Add item
                    if row.product_id:
                        items.append({
                            'customer_id': customer_id,
                            'order_id': order_id,
                            'product_id': str(row.product_id),
                            'category': row.category,
                            'product_type': row.product_type,
                            'quantity': int(row.quantity or 0),
                            'price': float(row.price or 0),
                            'refund_amount': float(row.refund_amount or 0)
                        })

                return {
                    'customers': list(customers),
                    'orders': list(orders_dict.values()),
                    'items': items,
                    'customer_orders': dict(customer_orders)
                }

            except Exception as e:
                logger.error(f"Failed to fetch order data: {e}", exc_info=True)
                return {
                    'customers': [],
                    'orders': [],
                    'items': [],
                    'customer_orders': {}
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
                        o.order_id,
                        o.order_date,
                        o.total_price,
                        o.discount_amount,
                        o.source,
                        oi.product_id,
                        oi.category,
                        oi.product_type,
                        oi.quantity,
                        oi.price,
                        oi.refund_amount
                    FROM orders o
                    LEFT JOIN order_items oi ON o.order_id = oi.order_id
                    WHERE o.store_id = :store_id
                      AND o.customer_id = :customer_id
                    ORDER BY o.order_date
                """)

                result = await db.execute(query, {
                    "store_id": store_id,
                    "customer_id": customer_id
                })
                rows = result.fetchall()

                orders_dict = {}
                items = []

                for row in rows:
                    order_id = str(row.order_id)

                    if order_id not in orders_dict:
                        orders_dict[order_id] = {
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

                return {'orders': list(orders_dict.values()), 'items': items}

            except Exception as e:
                logger.error(f"Failed to fetch customer orders: {e}", exc_info=True)
                return {'orders': [], 'items': []}


    async def _extract_all_customer_features(
        self,
        order_data: Dict[str, Any],
        axes_to_cluster: List[str]
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Extract features for all customers across specified axes.

        Returns:
            {
                axis_name: {
                    customer_id: {feature_name: value}
                }
            }
        """
        # Import feature extractor
        from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor

        feature_extractor = EcommerceFeatureExtractor()

        # Extract features for each customer
        customer_features = {axis: {} for axis in axes_to_cluster}

        for customer_id in order_data['customers']:
            # Get customer's orders and items
            customer_orders = order_data['customer_orders'].get(customer_id, [])
            customer_items = [item for item in order_data['items'] if item['customer_id'] == customer_id]

            if not customer_orders:
                continue

            # Extract all features
            features = feature_extractor.extract_all_features(
                customer_id,
                customer_orders,
                customer_items
            )

            # Organize by axis
            for axis_name in axes_to_cluster:
                if axis_name in features and features[axis_name]:
                    customer_features[axis_name][customer_id] = features[axis_name]

        return customer_features


    async def _cluster_axis(
        self,
        axis_name: str,
        customer_features: Dict[str, Dict[str, Dict[str, float]]],
        store_id: str
    ) -> List[DiscoveredSegment]:
        """
        Cluster customers along one behavioral axis.

        Returns:
            List of DiscoveredSegment objects
        """
        # Get features for this axis
        X_dict = customer_features.get(axis_name, {})

        if not X_dict:
            logger.warning(f"No features for axis {axis_name}")
            return []

        customer_ids = list(X_dict.keys())

        if len(customer_ids) < self.min_population:
            logger.warning(
                f"Insufficient customers with {axis_name} features: {len(customer_ids)}"
            )
            return []

        # Convert to matrix
        feature_names = list(next(iter(X_dict.values())).keys())
        X = np.array([[X_dict[cid][fname] for fname in feature_names] for cid in customer_ids])

        # Handle NaN/inf
        X = np.nan_to_num(X, nan=0.0, posinf=1e10, neginf=-1e10)

        # Preprocess features (with robust outlier handling if enabled)
        X_scaled, scaler_params = self._preprocess_features(X, axis_name)

        # Find optimal k (with dynamic range if enabled)
        optimal_k, silhouette = self._find_optimal_k(X_scaled, axis_name)

        if optimal_k < 2 or silhouette < self.min_silhouette:
            logger.warning(
                f"Poor clustering quality for {axis_name}: "
                f"k={optimal_k}, silhouette={silhouette:.3f}"
            )
            optimal_k = max(optimal_k, 2)

        logger.info(
            f"{axis_name}: optimal k={optimal_k}, silhouette={silhouette:.3f}"
        )

        # Cluster (FCM or K-Means based on configuration)
        fuzzy_memberships = None  # Will store FCM membership matrix if enabled

        if self.use_fuzzy_cmeans:
            # Use Fuzzy C-Means for soft clustering (enables temporal thumbprints)
            from backend.segmentation.fuzzy_cmeans_clustering import FuzzyCMeans

            fcm = FuzzyCMeans(
                n_clusters=optimal_k,
                m=self.fuzzy_m,
                max_iter=150,
                random_state=42
            )
            fcm.fit(X_scaled)
            labels = fcm.predict(X_scaled)  # Hard labels (argmax of fuzzy memberships)
            fuzzy_memberships = fcm.u_  # (n_customers, k) fuzzy membership matrix
            cluster_centers = fcm.cluster_centers_

            logger.info(f"{axis_name}: Fuzzy C-Means converged in {fcm.n_iter_} iterations")

        else:
            # Use K-Means for hard clustering (original algorithm)
            kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            cluster_centers = kmeans.cluster_centers_

        # Validate segment balance if robust scaling enabled
        if self.enable_robust_scaling:
            balance_ok = self._validate_segment_balance(labels, len(customer_ids), axis_name)
            if not balance_ok:
                logger.warning(f"{axis_name}: Segments unbalanced despite robust scaling")

        # scaler_params already set by _preprocess_features
        scaler_params['feature_names'] = feature_names
        scaler_params['silhouette'] = silhouette

        # Create segments
        segments = []
        for cluster_id in range(optimal_k):
            cluster_mask = labels == cluster_id
            cluster_customer_ids = [customer_ids[i] for i, m in enumerate(cluster_mask) if m]

            # Get cluster center (in original space for interpretation)
            cluster_center_scaled = cluster_centers[cluster_id]

            # Inverse transform using scaler params
            if scaler_params['type'] == 'robust':
                center = np.array(scaler_params['center'])
                scale = np.array(scaler_params['scale'])
                cluster_center_original = (cluster_center_scaled * scale) + center
            else:
                mean = np.array(scaler_params['mean'])
                scale = np.array(scaler_params['scale'])
                cluster_center_original = (cluster_center_scaled * scale) + mean

            # Generate AI-powered segment name and interpretation
            segment_name, interpretation = await self._name_segment_with_ai(
                axis_name,
                cluster_center_original,
                feature_names,
                X  # Population statistics
            )

            # Extract fuzzy memberships for this segment if FCM enabled
            customer_fuzzy_scores = None
            if fuzzy_memberships is not None:
                # Map fuzzy membership scores to customer IDs for this cluster
                customer_fuzzy_scores = {
                    str(customer_ids[i]): float(fuzzy_memberships[i, cluster_id])
                    for i in range(len(customer_ids))
                }

            segment = DiscoveredSegment(
                segment_id=f"{store_id}_{axis_name}_{segment_name}",
                axis_name=axis_name,
                segment_name=segment_name,
                cluster_center=cluster_center_scaled,  # Store scaled for membership calc
                feature_names=feature_names,
                scaler_params=scaler_params,
                population_percentage=len(cluster_customer_ids) / len(customer_ids),
                customer_count=len(cluster_customer_ids),
                interpretation=interpretation,
                fuzzy_membership_matrix=fuzzy_memberships,  # Full matrix (n_customers, k)
                customer_fuzzy_scores=customer_fuzzy_scores  # Scores for THIS segment
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
        Uses dynamic K optimizer if enabled.

        Returns:
            (optimal_k, best_silhouette)
        """
        if self.enable_dynamic_k and self.dynamic_k_optimizer:
            # Use dynamic K optimization
            result = self.dynamic_k_optimizer.find_optimal_k(X, axis_name)
            logger.info(f"{axis_name}: {result.recommendation}")
            return result.optimal_k, result.scores[result.optimal_k].get('silhouette', 0.0)

        # Fallback to original fixed k-range
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
                logger.warning(f"Failed to evaluate k={k}: {e}")
                continue

        return best_k, best_silhouette


    def _calculate_fuzzy_membership(
        self,
        customer_features: Dict[str, float],
        segments: List[DiscoveredSegment]
    ) -> Dict[str, float]:
        """
        Calculate fuzzy membership for customer across all segments in axis.

        Uses inverse distance weighting with exponential decay:
        - membership_i = exp(-distance_i) / Σ exp(-distance_j)

        Returns:
            {segment_name: membership_strength (0-1)}
        """
        # Convert customer features to vector
        feature_names = segments[0].feature_names
        customer_vector = np.array([customer_features.get(fname, 0) for fname in feature_names])

        # Handle NaN/inf
        customer_vector = np.nan_to_num(customer_vector, nan=0.0, posinf=1e10, neginf=-1e10)

        # Use POPULATION scaler from training
        scaler_params = segments[0].scaler_params
        scaler_type = scaler_params.get('type', 'standard')

        if scaler_type == 'robust':
            # RobustScaler: use center (median) and scale (IQR)
            center = np.array(scaler_params['center'])
            scale = np.array(scaler_params['scale'])
            customer_vector_scaled = (customer_vector - center) / scale
        else:
            # StandardScaler: use mean and std
            mean = np.array(scaler_params.get('mean', scaler_params.get('center', [])))
            scale = np.array(scaler_params['scale'])
            customer_vector_scaled = (customer_vector - mean) / scale

        # Calculate distances to all cluster centers
        distances = []
        for segment in segments:
            dist = np.linalg.norm(customer_vector_scaled - segment.cluster_center)
            distances.append(dist)

        # Convert distances to similarities (exponential decay)
        distances = np.array(distances)
        similarities = np.exp(-distances)

        # Normalize to sum to 1.0
        total = np.sum(similarities)
        memberships = similarities / total if total > 0 else np.ones(len(segments)) / len(segments)

        return {
            segments[i].segment_name: float(memberships[i])
            for i in range(len(segments))
        }


    async def _name_segment_with_ai(
        self,
        axis_name: str,
        cluster_center: np.ndarray,
        feature_names: List[str],
        population_X: np.ndarray
    ) -> Tuple[str, str]:
        """
        Use Claude API to generate segment name and interpretation.

        Falls back to generic names if AI naming disabled or fails.

        Returns:
            (segment_name, interpretation)
        """
        if not self.use_ai_naming or not self.anthropic_api_key:
            # Fallback to generic naming
            return self._generate_fallback_name(axis_name, cluster_center, feature_names)

        try:
            # Will implement AI naming in separate file
            from backend.segmentation.ai_segment_naming import name_segment_with_ai

            return await name_segment_with_ai(
                axis_name,
                cluster_center,
                feature_names,
                population_X,
                self.anthropic_api_key
            )

        except Exception as e:
            logger.warning(f"AI naming failed: {e}, using fallback")
            return self._generate_fallback_name(axis_name, cluster_center, feature_names)


    def _preprocess_features(
        self,
        X: np.ndarray,
        axis_name: str
    ) -> Tuple[np.ndarray, Dict]:
        """
        Preprocess features with optional robust outlier handling.

        Returns:
            (X_scaled, scaler_params)
        """
        if not self.enable_robust_scaling:
            # Original behavior: StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            return X_scaled, {
                'type': 'standard',
                'mean': scaler.mean_.tolist(),
                'scale': scaler.scale_.tolist()
            }

        # Robust outlier handling
        X_clean = X.copy()
        winsorize_limits = {}

        # Winsorize extreme values (per feature)
        for feat_idx in range(X_clean.shape[1]):
            feature_values = X_clean[:, feat_idx]
            lower_limit = np.percentile(feature_values, 100 - self.winsorize_percentile)
            upper_limit = np.percentile(feature_values, self.winsorize_percentile)

            # Cap values
            X_clean[:, feat_idx] = np.clip(feature_values, lower_limit, upper_limit)
            winsorize_limits[feat_idx] = {
                'lower': float(lower_limit),
                'upper': float(upper_limit)
            }

        # Use RobustScaler (median/IQR instead of mean/std)
        scaler = RobustScaler()
        X_scaled = scaler.fit_transform(X_clean)

        return X_scaled, {
            'type': 'robust',
            'center': scaler.center_.tolist(),
            'scale': scaler.scale_.tolist(),
            'winsorize_limits': winsorize_limits
        }

    def _validate_segment_balance(
        self,
        labels: np.ndarray,
        n_samples: int,
        axis_name: str
    ) -> bool:
        """
        Validate that segments are balanced (not "everyone vs outliers").

        Returns:
            True if balanced, False otherwise
        """
        from collections import Counter
        segment_counts = Counter(labels)
        segment_sizes = list(segment_counts.values())

        largest_pct = max(segment_sizes) / n_samples * 100
        smallest_pct = min(segment_sizes) / n_samples * 100

        is_balanced = (
            largest_pct <= self.max_dominant_segment_pct and
            smallest_pct >= self.min_segment_size_pct
        )

        if not is_balanced:
            logger.warning(
                f"{axis_name}: Unbalanced segments - largest={largest_pct:.1f}%, "
                f"smallest={smallest_pct:.1f}%"
            )

        return is_balanced

    def _generate_fallback_name(
        self,
        axis_name: str,
        cluster_center: np.ndarray,
        feature_names: List[str]
    ) -> Tuple[str, str]:
        """Generate generic segment name without AI"""
        # Simple heuristic: use first feature value to classify
        if len(cluster_center) == 0:
            return f"{axis_name}_segment_unknown", "Segment with insufficient data"

        primary_value = cluster_center[0]
        primary_feature = feature_names[0]

        # High/medium/low classification
        if primary_value > 0.5:
            level = "high"
        elif primary_value > -0.5:
            level = "medium"
        else:
            level = "low"

        segment_name = f"{level}_{axis_name}"
        interpretation = f"Customers with {level} {primary_feature}"

        return segment_name, interpretation


    def _generate_interpretation(
        self,
        axis_profiles: Dict[str, CustomerAxisProfile]
    ) -> str:
        """Generate human-readable interpretation from axis profiles"""
        parts = []

        # Collect dominant segments from key axes
        key_axes = [
            'purchase_frequency',
            'purchase_value',
            'loyalty_trajectory',
            'customer_maturity'
        ]

        for axis in key_axes:
            if axis in axis_profiles:
                segment = axis_profiles[axis].dominant_segment.replace('_', ' ')
                parts.append(segment)

        if not parts:
            return "Multi-dimensional customer profile"

        return ', '.join(parts)


    async def _store_discovered_segments(
        self,
        store_id: str,
        discovered_segments: Dict[str, List[DiscoveredSegment]]
    ):
        """Store discovered segments in database"""
        # TODO: Implement database storage
        # Store in dim_segment_master table
        logger.info(f"Storing {sum(len(segs) for segs in discovered_segments.values())} segments")
        pass


    async def _load_discovered_segments(
        self,
        store_id: str
    ) -> Dict[str, List[DiscoveredSegment]]:
        """Load previously discovered segments from database"""
        # TODO: Implement database loading
        logger.info(f"Loading discovered segments for {store_id}")
        return {}


    async def _store_customer_profile(
        self,
        profile: CustomerMultiAxisProfile,
        store_id: str
    ):
        """Store customer profile in database (populate JSONB columns)"""
        # TODO: Implement database storage
        # Update customer_profiles table
        logger.info(f"Storing profile for customer {profile.customer_id}")
        pass


    def _noop_context(self):
        """No-op context manager for when db_session is provided"""
        from contextlib import contextmanager

        @contextmanager
        def noop():
            yield None

        return noop()
