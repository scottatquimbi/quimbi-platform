"""
Multi-Axis Clustering Engine

Discovers behavioral segments by clustering players independently in each
feature space (axis). Uses fuzzy membership so players belong to ALL segments
with varying strengths (0.0-1.0).

Core Algorithm:
1. Extract features for all players across all axes
2. For each axis independently:
   - Normalize features
   - Find optimal k (number of clusters) using silhouette score
   - Cluster players using KMeans
   - Calculate fuzzy membership (distance-based, sum to 1.0 per axis)
   - Interpret clusters (examine centroids, generate labels)
3. Store discovered segments and player memberships

Author: Quimbi Platform
Version: 3.0.0 (Multi-Axis)
Date: October 14, 2025
"""

import numpy as np
import logging
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
from backend.core.multi_axis_feature_extraction import FeatureExtractor
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
    player_count: int
    interpretation: str


@dataclass
class PlayerAxisProfile:
    """Player's fuzzy membership profile for one axis"""
    player_id: str
    axis_name: str
    memberships: Dict[str, float]  # {segment_name: membership_strength}
    dominant_segment: str
    features: Dict[str, float]
    calculated_at: datetime


@dataclass
class PlayerMultiAxisProfile:
    """Player's complete profile across all axes"""
    player_id: str
    game_id: str
    axis_profiles: Dict[str, PlayerAxisProfile]  # {axis_name: profile}
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
    Players get fuzzy membership in all segments per axis.

    FIX: Clustering parameters are now configurable to support different games
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
        session_gap_minutes: int = 30
    ):
        """
        Initialize clustering engine with configurable parameters.

        Args:
            db_session: Database session (optional)
            min_k: Minimum clusters per axis (default: 2)
            max_k: Maximum clusters per axis (default: 6)
            min_silhouette: Minimum acceptable silhouette score (default: 0.3)
            min_population: Minimum players required for discovery (default: 100)
            session_gap_minutes: Gap threshold for session detection (default: 30)
        """
        self.db_session = db_session

        # FIX: Pass session_gap_minutes to feature extractor
        self.feature_extractor = FeatureExtractor(
            gap_threshold_minutes=session_gap_minutes
        )

        # Clustering parameters (now configurable)
        self.min_k = min_k
        self.max_k = max_k
        self.min_silhouette = min_silhouette
        self.min_population = min_population


    async def discover_multi_axis_segments(
        self,
        game_id: str,
        game_launch_date: Optional[datetime] = None
    ) -> Dict[str, List[DiscoveredSegment]]:
        """
        Main entry point: Discover segments across all axes.

        Args:
            game_id: Game identifier
            game_launch_date: Launch date (for purchase timing axis)

        Returns:
            Dict mapping axis name to list of discovered segments
        """
        logger.info(f"Starting multi-axis segmentation for game {game_id}")

        # Step 1: Fetch event data
        event_data = await self._fetch_event_data(game_id)

        if len(event_data['players']) < self.min_population:
            logger.warning(
                f"Insufficient population ({len(event_data['players'])} players)"
            )
            return {}

        logger.info(
            f"Loaded {len(event_data['events'])} events from "
            f"{len(event_data['players'])} players, "
            f"{len(event_data['event_type_counts'])} event types"
        )

        # Step 2: Extract features for all players across all axes
        all_event_types = list(event_data['event_type_counts'].keys())
        player_features = await self._extract_all_player_features(
            event_data,
            all_event_types,
            game_launch_date
        )

        logger.info(f"Extracted features for {len(player_features)} players")

        # Step 3: Cluster each axis independently
        discovered_segments = {}

        axes_to_cluster = [
            'feature_engagement',
            'temporal_patterns',
            'intensity_patterns',
            'progression_velocity',
            'content_consumption',
            'learning_curve',
            'volatility'
        ]

        if game_launch_date:
            axes_to_cluster.append('purchase_timing')

        for axis_name in axes_to_cluster:
            logger.info(f"Clustering axis: {axis_name}")

            segments = await self._cluster_axis(
                axis_name,
                player_features,
                game_id
            )

            if segments:
                discovered_segments[axis_name] = segments
                logger.info(
                    f"Discovered {len(segments)} segments for {axis_name}"
                )
            else:
                logger.warning(f"No segments discovered for {axis_name}")

        # Step 4: Store discovered segments
        await self._store_discovered_segments(game_id, discovered_segments)

        logger.info(
            f"Multi-axis discovery complete: {len(discovered_segments)} axes, "
            f"{sum(len(segs) for segs in discovered_segments.values())} total segments"
        )

        return discovered_segments


    async def calculate_player_profile(
        self,
        player_id: str,
        game_id: str,
        game_launch_date: Optional[datetime] = None,
        store_profile: bool = False
    ) -> PlayerMultiAxisProfile:
        """
        Calculate individual player's fuzzy membership profile across all axes.

        Args:
            player_id: Player identifier
            game_id: Game identifier
            game_launch_date: Launch date (for purchase timing)
            store_profile: If True, save profile to database

        Returns:
            PlayerMultiAxisProfile with fuzzy memberships
        """
        logger.info(f"Calculating profile for player {player_id}")

        # Step 1: Get player's events
        event_data = await self._fetch_player_events(player_id, game_id)

        if not event_data['events']:
            logger.warning(f"No events found for player {player_id}")
            return None

        # Step 2: Get all event types (for feature extraction context)
        all_event_types = await self._get_all_event_types(game_id)

        # Step 3: Extract features
        features = self.feature_extractor.extract_all_features(
            event_data['events'],
            all_event_types,
            game_launch_date
        )

        # Step 4: Load discovered segments for this game
        discovered_segments = await self._load_discovered_segments(game_id)

        # Step 5: Calculate fuzzy membership for each axis
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

            axis_profiles[axis_name] = PlayerAxisProfile(
                player_id=player_id,
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

        # Step 6: Generate interpretation
        interpretation = self._generate_interpretation(axis_profiles)

        profile = PlayerMultiAxisProfile(
            player_id=player_id,
            game_id=game_id,
            axis_profiles=axis_profiles,
            dominant_segments=dominant_segments,
            fuzzy_memberships=fuzzy_memberships,
            top2_segments=top2_segments,
            membership_strength=membership_strength,
            interpretation=interpretation,
            calculated_at=datetime.now(timezone.utc)
        )

        # Step 7: Store profile if requested
        if store_profile:
            await self._store_player_profile(profile, game_id)

        return profile


    async def _fetch_event_data(
        self,
        game_id: str,
        lookback_days: int = None
    ) -> Dict[str, Any]:
        """
        Fetch event data for all players.

        Args:
            game_id: Game identifier
            lookback_days: Optional number of days to look back (None = all data)
        """
        async with get_db_session() if not self.db_session else self._noop_context() as session:
            db = session or self.db_session

            try:
                # Build query with optional date filter
                if lookback_days:
                    query = text(f"""
                        SELECT
                            player_id,
                            event_type,
                            event_timestamp,
                            event_data
                        FROM player_behavior_events
                        WHERE
                            game_id = :game_id
                            AND event_date >= NOW() - INTERVAL '{lookback_days} days'
                        ORDER BY player_id, event_timestamp
                        LIMIT 500000
                    """)
                else:
                    # No date filter - use ALL data
                    query = text("""
                        SELECT
                            player_id,
                            event_type,
                            event_timestamp,
                            event_data
                        FROM player_behavior_events
                        WHERE
                            game_id = :game_id
                        ORDER BY player_id, event_timestamp
                        LIMIT 500000
                    """)

                result = await db.execute(query, {"game_id": game_id})
                rows = result.fetchall()

                # Organize data
                events = []
                players = set()
                event_type_counts = defaultdict(int)
                player_events = defaultdict(list)

                for row in rows:
                    player_id = str(row.player_id)
                    event_type = row.event_type

                    players.add(player_id)
                    event_type_counts[event_type] += 1

                    event = {
                        'player_id': player_id,
                        'event_type': event_type,
                        'timestamp': row.event_timestamp,
                        'data': row.event_data
                    }

                    events.append(event)
                    player_events[player_id].append(event)

                return {
                    'players': list(players),
                    'events': events,
                    'event_type_counts': dict(event_type_counts),
                    'player_events': dict(player_events)
                }

            except Exception as e:
                logger.error(f"Failed to fetch event data: {e}", exc_info=True)
                return {
                    'players': [],
                    'events': [],
                    'event_type_counts': {},
                    'player_events': {}
                }


    async def _fetch_player_events(
        self,
        player_id: str,
        game_id: str
    ) -> Dict[str, Any]:
        """Fetch events for single player"""
        async with get_db_session() if not self.db_session else self._noop_context() as session:
            db = session or self.db_session

            try:
                query = text("""
                    SELECT
                        event_type,
                        event_timestamp,
                        event_data
                    FROM player_behavior_events
                    WHERE
                        game_id = :game_id
                        AND player_id = :player_id
                    ORDER BY event_timestamp
                """)

                result = await db.execute(query, {
                    "game_id": game_id,
                    "player_id": player_id
                })
                rows = result.fetchall()

                events = []
                for row in rows:
                    events.append({
                        'player_id': player_id,
                        'event_type': row.event_type,
                        'timestamp': row.event_timestamp,
                        'data': row.event_data
                    })

                return {'events': events}

            except Exception as e:
                logger.error(f"Failed to fetch player events: {e}", exc_info=True)
                return {'events': []}


    async def _get_all_event_types(self, game_id: str) -> List[str]:
        """Get all event types for this game"""
        async with get_db_session() if not self.db_session else self._noop_context() as session:
            db = session or self.db_session

            try:
                query = text("""
                    SELECT DISTINCT event_type
                    FROM player_behavior_events
                    WHERE game_id = :game_id
                """)

                result = await db.execute(query, {"game_id": game_id})
                rows = result.fetchall()

                return [row.event_type for row in rows]

            except Exception as e:
                logger.error(f"Failed to fetch event types: {e}", exc_info=True)
                return []


    async def _extract_all_player_features(
        self,
        event_data: Dict[str, Any],
        all_event_types: List[str],
        game_launch_date: Optional[datetime]
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Extract features for all players across all axes.

        Returns:
            {player_id: {axis_name: {feature_name: value}}}
        """
        player_features = {}

        for player_id, player_events in event_data['player_events'].items():
            try:
                features = self.feature_extractor.extract_all_features(
                    player_events,
                    all_event_types,
                    game_launch_date
                )
                player_features[player_id] = features

            except Exception as e:
                logger.error(
                    f"Failed to extract features for player {player_id}: {e}",
                    exc_info=True
                )

        return player_features


    async def _cluster_axis(
        self,
        axis_name: str,
        player_features: Dict[str, Dict[str, Dict[str, float]]],
        game_id: str
    ) -> List[DiscoveredSegment]:
        """
        Cluster players on one axis.

        Returns list of discovered segments for this axis.
        """
        # Step 1: Extract features for this axis from all players
        X_dict = {}
        player_ids = []

        for player_id, all_features in player_features.items():
            if axis_name not in all_features:
                continue

            axis_features = all_features[axis_name]
            if not axis_features:
                continue

            X_dict[player_id] = axis_features
            player_ids.append(player_id)

        if len(player_ids) < self.min_population:
            logger.warning(
                f"Insufficient players with {axis_name} features: {len(player_ids)}"
            )
            return []

        # Step 2: Convert to matrix
        feature_names = list(next(iter(X_dict.values())).keys())
        X = np.array([[X_dict[pid][fname] for fname in feature_names] for pid in player_ids])

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
            cluster_player_ids = [player_ids[i] for i, m in enumerate(cluster_mask) if m]

            # Interpret cluster
            cluster_center_scaled = kmeans.cluster_centers_[cluster_id]
            cluster_center_original = scaler.inverse_transform(
                cluster_center_scaled.reshape(1, -1)
            )[0]

            segment_name, interpretation = self._interpret_cluster(
                axis_name,
                cluster_center_original,
                feature_names
            )

            segment = DiscoveredSegment(
                segment_id=f"{game_id}_{axis_name}_{segment_name}",
                axis_name=axis_name,
                segment_name=segment_name,
                cluster_center=cluster_center_scaled,  # Store scaled for membership calc
                feature_names=feature_names,
                scaler_params=scaler_params,  # FIX: Store population scaler
                population_percentage=len(cluster_player_ids) / len(player_ids),
                player_count=len(cluster_player_ids),
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


    def _interpret_cluster(
        self,
        axis_name: str,
        cluster_center: np.ndarray,
        feature_names: List[str]
    ) -> Tuple[str, str]:
        """
        Interpret cluster by examining centroid features.

        Returns (segment_name, interpretation)
        """
        # Create dict of feature values
        features = {name: cluster_center[i] for i, name in enumerate(feature_names)}

        # Find defining features (highest/lowest values)
        sorted_features = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)
        top_features = sorted_features[:3]

        # Axis-specific interpretation
        if axis_name == 'temporal_patterns':
            return self._interpret_temporal_cluster(features, top_features)
        elif axis_name == 'intensity_patterns':
            return self._interpret_intensity_cluster(features, top_features)
        elif axis_name == 'progression_velocity':
            return self._interpret_progression_cluster(features, top_features)
        elif axis_name == 'content_consumption':
            return self._interpret_content_cluster(features, top_features)
        elif axis_name == 'learning_curve':
            return self._interpret_learning_cluster(features, top_features)
        elif axis_name == 'volatility':
            return self._interpret_volatility_cluster(features, top_features)
        elif axis_name == 'purchase_timing':
            return self._interpret_purchase_cluster(features, top_features)
        else:
            return ('segment', 'Behavioral cluster')


    def _interpret_temporal_cluster(self, features, top_features):
        """Interpret temporal pattern cluster"""
        weekend_ratio = features.get('weekend_ratio', 0)
        session_length = features.get('avg_session_length_min', 0)

        if weekend_ratio > 0.6:
            name = "weekend_warrior"
            desc = f"Plays primarily on weekends ({weekend_ratio*100:.0f}% weekend)"
        elif session_length > 180:
            name = "binge_player"
            desc = f"Long play sessions (avg {session_length:.0f} minutes)"
        elif features.get('play_frequency', 0) > 0.8:
            name = "consistent_daily"
            desc = f"Plays daily ({features.get('play_frequency', 0)*100:.0f}% of days)"
        else:
            name = "weekday_regular"
            desc = "Regular weekday player"

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
            name = "patient_gamer"
            desc = f"Patient gamer ({days_after:.0f} days after launch)"
        else:
            name = "late_adopter"
            desc = f"Late adopter ({days_after:.0f} days after launch)"

        return name, desc


    def _calculate_fuzzy_membership(
        self,
        player_features: Dict[str, float],
        segments: List[DiscoveredSegment]
    ) -> Dict[str, float]:
        """
        Calculate fuzzy membership for player across all segments in axis.

        CRITICAL FIX: Uses population scaler from training to standardize player features,
        ensuring they're in the same coordinate space as cluster centers.

        Uses inverse distance weighting:
        - Close to cluster center = high membership
        - Far from cluster center = low membership
        - Memberships sum to 1.0

        Returns:
            {segment_name: membership_strength}
        """
        # Convert player features to vector
        feature_names = segments[0].feature_names
        player_vector = np.array([player_features.get(fname, 0) for fname in feature_names])

        # Handle NaN/inf
        player_vector = np.nan_to_num(player_vector, nan=0.0, posinf=1e10, neginf=-1e10)

        # CRITICAL FIX: Use POPULATION scaler from training, not player's own statistics
        # All segments in an axis share the same scaler params
        scaler_params = segments[0].scaler_params
        mean = np.array(scaler_params['mean'])
        scale = np.array(scaler_params['scale'])

        # Standardize using population statistics (same as training)
        player_vector_scaled = (player_vector - mean) / scale

        # Calculate distances to all cluster centers
        distances = []
        for segment in segments:
            dist = np.linalg.norm(player_vector_scaled - segment.cluster_center)
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
        axis_profiles: Dict[str, PlayerAxisProfile]
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
        game_id: str,
        discovered_segments: Dict[str, List[DiscoveredSegment]]
    ):
        """Store discovered segments in database"""
        if not discovered_segments:
            logger.warning("No segments to store")
            return

        # Use existing session or create new one
        if self.db_session:
            async with self._noop_context():
                await self._store_segments_impl(self.db_session, game_id, discovered_segments)
        else:
            async with get_db_session() as session:
                await self._store_segments_impl(session, game_id, discovered_segments)

    async def _store_segments_impl(self, session, game_id, discovered_segments):
        """Implementation of segment storage"""
        try:
            # Delete existing segments for this game (replace strategy)
            await session.execute(
                text("DELETE FROM multi_axis_segments WHERE game_id = :game_id"),
                {"game_id": game_id}
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
                                segment_id, game_id, axis_name, segment_name,
                                cluster_center, feature_names, scaler_params, population_percentage,
                                player_count, interpretation, created_at, updated_at
                            ) VALUES (
                                :segment_id, :game_id, :axis_name, :segment_name,
                                :cluster_center, :feature_names, :scaler_params, :population_percentage,
                                :player_count, :interpretation, NOW(), NOW()
                            )
                        """),
                        {
                            "segment_id": str(uuid.uuid4()),
                            "game_id": game_id,
                            "axis_name": axis_name,
                            "segment_name": segment_name,
                            "cluster_center": json.dumps(cluster_center_list),
                            "feature_names": json.dumps(segment.feature_names),
                            "scaler_params": json.dumps(segment.scaler_params),  # FIX: Store scaler params
                            "population_percentage": segment.population_percentage,
                            "player_count": segment.player_count,
                            "interpretation": segment.interpretation
                        }
                    )

            # Commit within the transaction
            await session.flush()

            total_segments = sum(len(segs) for segs in discovered_segments.values())
            logger.info(
                f"Stored {total_segments} segments across {len(discovered_segments)} axes "
                f"for game {game_id}"
            )

        except Exception as e:
            logger.error(f"Error storing segments: {e}")
            raise


    async def _load_discovered_segments(
        self,
        game_id: str
    ) -> Dict[str, List[DiscoveredSegment]]:
        """Load discovered segments from database"""
        # Use existing session or create new one
        if self.db_session:
            async with self._noop_context():
                return await self._load_segments_impl(self.db_session, game_id)
        else:
            async with get_db_session() as session:
                return await self._load_segments_impl(session, game_id)

    async def _load_segments_impl(self, session, game_id):
        """Implementation of segment loading"""
        try:
            result = await session.execute(
                text("""
                    SELECT
                        segment_id, axis_name, segment_name, cluster_center,
                        feature_names, scaler_params, population_percentage, player_count, interpretation
                    FROM multi_axis_segments
                    WHERE game_id = :game_id
                    ORDER BY axis_name, segment_name
                """),
                {"game_id": game_id}
            )

            rows = result.fetchall()

            if not rows:
                logger.info(f"No segments found for game {game_id}")
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
                    player_count=row[7],
                    interpretation=row[8]
                )

                discovered_segments[row[1]].append(segment)

            logger.info(
                f"Loaded {len(rows)} segments across {len(discovered_segments)} axes "
                f"for game {game_id}"
            )

            return dict(discovered_segments)

        except Exception as e:
            logger.error(f"Error loading segments: {e}")
            raise


    async def _store_player_profile(
        self,
        profile: PlayerMultiAxisProfile,
        game_id: str
    ):
        """Store player's fuzzy membership profile in database"""
        if not profile or not profile.axis_profiles:
            logger.warning("No profile to store")
            return

        # Use existing session or create new one
        if self.db_session:
            async with self._noop_context():
                await self._store_profile_impl(self.db_session, profile, game_id)
        else:
            async with get_db_session() as session:
                await self._store_profile_impl(session, profile, game_id)

    async def _store_profile_impl(self, session, profile, game_id):
        """Implementation of profile storage"""
        try:
            # Delete existing memberships for this player (replace strategy)
            await session.execute(
                text("""
                    DELETE FROM player_axis_memberships
                    WHERE player_id = :player_id AND game_id = :game_id
                """),
                {"player_id": profile.player_id, "game_id": game_id}
            )

            # Insert new memberships for each axis
            for axis_name, axis_profile in profile.axis_profiles.items():
                await session.execute(
                    text("""
                        INSERT INTO player_axis_memberships (
                            membership_id, player_id, game_id, axis_name,
                            memberships, dominant_segment, features, calculated_at
                        ) VALUES (
                            :membership_id, :player_id, :game_id, :axis_name,
                            :memberships, :dominant_segment, :features, :calculated_at
                        )
                    """),
                    {
                        "membership_id": str(uuid.uuid4()),
                        "player_id": profile.player_id,
                        "game_id": game_id,
                        "axis_name": axis_name,
                        "memberships": json.dumps(axis_profile.memberships),
                        "dominant_segment": axis_profile.dominant_segment,
                        "features": json.dumps(axis_profile.features),
                        "calculated_at": axis_profile.calculated_at
                    }
                )

            await session.flush()

            logger.info(
                f"Stored profile for player {profile.player_id} across "
                f"{len(profile.axis_profiles)} axes"
            )

        except Exception as e:
            logger.error(f"Error storing player profile: {e}")
            raise


    async def _log_discovery_run(
        self,
        run_id: str,
        game_id: str,
        player_count: int,
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
                    self.db_session, run_id, game_id, player_count, event_count,
                    axes_discovered, total_segments, avg_silhouette_score,
                    started_at, status, error_message, processing_time_seconds
                )
        else:
            async with get_db_session() as session:
                await self._log_run_impl(
                    session, run_id, game_id, player_count, event_count,
                    axes_discovered, total_segments, avg_silhouette_score,
                    started_at, status, error_message, processing_time_seconds
                )

    async def _log_run_impl(
        self, session, run_id, game_id, player_count, event_count,
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
                        run_id, game_id, player_count, event_count,
                        axes_discovered, total_segments, avg_silhouette_score,
                        discovery_started_at, discovery_completed_at,
                        processing_time_seconds, status, error_message
                    ) VALUES (
                        :run_id, :game_id, :player_count, :event_count,
                        :axes_discovered, :total_segments, :avg_silhouette_score,
                        :discovery_started_at, :discovery_completed_at,
                        :processing_time_seconds, :status, :error_message
                    )
                """),
                {
                    "run_id": run_id,
                    "game_id": game_id,
                    "player_count": player_count,
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
