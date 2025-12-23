"""
Multi-Axis Feature Extraction Engine

Extracts behavioral features across 7 independent dimensions:
1. Feature Engagement Distribution - What product features they use
2. Temporal Patterns - When they engage (weekend warrior, binge player, etc.)
3. Intensity Patterns - How much they engage (hardcore, casual, declining, etc.)
4. Progression Velocity - How they progress (rusher, completionist, etc.)
5. Content Consumption Velocity - How fast they consume content
6. Learning Curve - How quickly they master the product
7. Volatility/Stability - How consistent their behavior is

Each feature space is independent and discovers natural behavioral clusters
without hardcoded assumptions about what segments should exist.

Author: Quimbi Platform
Version: 3.0.0 (Multi-Axis)
Date: October 14, 2025
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import statistics
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PlayerSession:
    """A detected play session"""
    start_time: datetime
    end_time: datetime
    events: List[Dict[str, Any]]
    duration_minutes: float
    event_count: int


class SessionDetector:
    """
    Detects play sessions from event timestamps using gap-based approach.

    A new session starts when gap between events exceeds threshold.
    """

    def __init__(self, gap_threshold_minutes: int = 30):
        """
        Args:
            gap_threshold_minutes: Inactivity gap that defines new session (default 30min)
        """
        self.gap_threshold_minutes = gap_threshold_minutes


    def detect_sessions(self, player_events: List[Dict[str, Any]]) -> List[PlayerSession]:
        """
        Detect play sessions from player events.

        Args:
            player_events: List of events with 'timestamp' field

        Returns:
            List of PlayerSession objects
        """
        if not player_events:
            return []

        # Sort events by timestamp
        sorted_events = sorted(player_events, key=lambda e: e['timestamp'])

        sessions = []
        current_session_events = [sorted_events[0]]

        for i in range(1, len(sorted_events)):
            current_event = sorted_events[i]
            previous_event = sorted_events[i-1]

            # Calculate time gap
            time_gap = (current_event['timestamp'] - previous_event['timestamp']).total_seconds() / 60

            if time_gap > self.gap_threshold_minutes:
                # New session - save current session
                session = self._create_session(current_session_events)
                sessions.append(session)

                # Start new session
                current_session_events = [current_event]
            else:
                # Same session
                current_session_events.append(current_event)

        # Don't forget last session
        if current_session_events:
            session = self._create_session(current_session_events)
            sessions.append(session)

        return sessions


    def _create_session(self, events: List[Dict[str, Any]]) -> PlayerSession:
        """Create PlayerSession object from events"""
        start_time = events[0]['timestamp']
        end_time = events[-1]['timestamp']
        duration_minutes = (end_time - start_time).total_seconds() / 60

        return PlayerSession(
            start_time=start_time,
            end_time=end_time,
            events=events,
            duration_minutes=max(duration_minutes, 1.0),  # Minimum 1 minute
            event_count=len(events)
        )


class FeatureExtractor:
    """
    Extract features across multiple behavioral dimensions.

    Each extract_* method returns features for one axis.
    Features are normalized and ready for clustering.

    FIX: Parameters are now configurable instead of hard-coded.
    """

    def __init__(
        self,
        gap_threshold_minutes: int = 30,
        # Content exhaustion thresholds (configurable)
        exhaustion_tenure_threshold_days: int = 30,
        exhaustion_coverage_high: float = 0.7,
        exhaustion_coverage_very_high: float = 0.8,
        exhaustion_coverage_complete: float = 0.9
    ):
        """
        Initialize feature extractor with configurable parameters.

        Args:
            gap_threshold_minutes: Inactivity gap for session detection (default: 30)
            exhaustion_tenure_threshold_days: Tenure cutoff for exhaustion risk (default: 30)
            exhaustion_coverage_high: Coverage threshold for high exhaustion risk (default: 0.7)
            exhaustion_coverage_very_high: Coverage for very high risk (default: 0.8)
            exhaustion_coverage_complete: Coverage for complete exhaustion (default: 0.9)
        """
        self.session_detector = SessionDetector(gap_threshold_minutes=gap_threshold_minutes)

        # Store exhaustion thresholds
        self.exhaustion_tenure_threshold = exhaustion_tenure_threshold_days
        self.exhaustion_coverage_high = exhaustion_coverage_high
        self.exhaustion_coverage_very_high = exhaustion_coverage_very_high
        self.exhaustion_coverage_complete = exhaustion_coverage_complete


    def extract_all_features(
        self,
        player_events: List[Dict[str, Any]],
        all_event_types: List[str],
        game_launch_date: Optional[datetime] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Extract features for all 7 axes.

        Args:
            player_events: List of events for this player
            all_event_types: All event types in the game (for diversity calculation)
            game_launch_date: Game launch date (for purchase timing axis)

        Returns:
            Dict mapping axis name to feature dict
        """
        if not player_events:
            return {}

        features = {}

        # Extract features for each axis
        features['feature_engagement'] = self.extract_feature_engagement(
            player_events, all_event_types
        )

        features['temporal_patterns'] = self.extract_temporal_features(player_events)
        features['intensity_patterns'] = self.extract_intensity_features(player_events)
        features['progression_velocity'] = self.extract_progression_features(
            player_events, all_event_types
        )
        features['content_consumption'] = self.extract_content_consumption_features(
            player_events, all_event_types
        )
        features['learning_curve'] = self.extract_learning_curve_features(player_events)
        features['volatility'] = self.extract_volatility_features(player_events)

        if game_launch_date:
            features['purchase_timing'] = self.extract_purchase_timing_features(
                player_events, game_launch_date
            )

        return features


    def extract_feature_engagement(
        self,
        player_events: List[Dict[str, Any]],
        all_event_types: List[str]
    ) -> Dict[str, float]:
        """
        Extract feature engagement distribution.

        Instead of hardcoding "story" or "combat", measures distribution
        across all available event types. Clustering will discover natural
        feature groupings.

        Features:
            - Percentage of events per event type
            - Event type diversity metrics
        """
        if not player_events:
            return {}

        total_events = len(player_events)
        event_type_counts = Counter(e['event_type'] for e in player_events)

        features = {}

        # Event type distribution (percentage for each type)
        for event_type in all_event_types:
            count = event_type_counts.get(event_type, 0)
            features[f'event_type_{event_type}_pct'] = count / total_events

        # Diversity metrics
        unique_types = len(event_type_counts)
        features['event_type_diversity'] = unique_types / max(len(all_event_types), 1)

        # Entropy (measure of distribution uniformity)
        probabilities = [count / total_events for count in event_type_counts.values()]
        entropy = -sum(p * np.log2(p) for p in probabilities if p > 0)
        max_entropy = np.log2(len(all_event_types)) if len(all_event_types) > 0 else 1
        features['event_distribution_entropy'] = entropy / max_entropy if max_entropy > 0 else 0

        # Concentration (Herfindahl index - measures if focused on few event types)
        features['event_concentration'] = sum(p ** 2 for p in probabilities)

        return features


    def extract_temporal_features(
        self,
        player_events: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Extract temporal pattern features.

        Captures WHEN they play without hardcoding "weekend warrior" segments.
        Clustering will discover natural temporal patterns.

        Features:
            - Hour of day distribution (24 bins)
            - Day of week distribution (7 bins)
            - Session patterns
            - Play consistency metrics
        """
        if not player_events:
            return {}

        features = {}
        timestamps = [e['timestamp'] for e in player_events]
        sessions = self.session_detector.detect_sessions(player_events)

        # Hour of day distribution (0-23)
        hours = [ts.hour for ts in timestamps]
        hour_distribution = Counter(hours)
        for hour in range(24):
            features[f'hour_{hour}_pct'] = hour_distribution.get(hour, 0) / len(timestamps)

        # Day of week distribution (0=Monday, 6=Sunday)
        days = [ts.weekday() for ts in timestamps]
        day_distribution = Counter(days)
        for day in range(7):
            features[f'day_{day}_pct'] = day_distribution.get(day, 0) / len(timestamps)

        # Derived temporal patterns
        weekend_events = sum(1 for day in days if day >= 5)  # Sat/Sun
        features['weekend_ratio'] = weekend_events / len(days)
        features['weekday_ratio'] = 1.0 - features['weekend_ratio']

        # Session patterns
        if sessions:
            features['session_count'] = len(sessions)
            features['avg_session_length_min'] = statistics.mean(s.duration_minutes for s in sessions)
            features['session_length_variance'] = statistics.variance(s.duration_minutes for s in sessions) if len(sessions) > 1 else 0

            # Inter-session gaps
            if len(sessions) > 1:
                gaps = []
                for i in range(1, len(sessions)):
                    gap_hours = (sessions[i].start_time - sessions[i-1].end_time).total_seconds() / 3600
                    gaps.append(gap_hours)

                features['avg_inter_session_gap_hours'] = statistics.mean(gaps)
                features['inter_session_gap_variance'] = statistics.variance(gaps) if len(gaps) > 1 else 0
            else:
                features['avg_inter_session_gap_hours'] = 0
                features['inter_session_gap_variance'] = 0
        else:
            features['session_count'] = 0
            features['avg_session_length_min'] = 0
            features['session_length_variance'] = 0
            features['avg_inter_session_gap_hours'] = 0
            features['inter_session_gap_variance'] = 0

        # Play consistency
        unique_dates = len(set(ts.date() for ts in timestamps))
        first_event = min(timestamps)
        last_event = max(timestamps)
        tenure_days = (last_event - first_event).days + 1

        features['play_days_count'] = unique_dates
        features['play_frequency'] = unique_dates / max(tenure_days, 1)  # Ratio of days played

        # Streak analysis
        play_dates = sorted(set(ts.date() for ts in timestamps))
        streaks = self._calculate_streaks(play_dates)
        features['max_play_streak_days'] = max(streaks) if streaks else 0
        features['avg_play_streak_days'] = statistics.mean(streaks) if streaks else 0

        return features


    def extract_intensity_features(
        self,
        player_events: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Extract intensity pattern features.

        Captures HOW MUCH they play without hardcoding "hardcore" or "casual".
        Clustering will discover natural intensity levels.

        Features:
            - Events per day
            - Intensity trend (increasing, stable, declining)
            - Intensity variance
            - Recent vs historical intensity
        """
        if not player_events:
            return {}

        features = {}
        timestamps = [e['timestamp'] for e in player_events]

        # Basic intensity
        first_event = min(timestamps)
        last_event = max(timestamps)
        tenure_days = (last_event - first_event).days + 1

        features['total_events'] = len(player_events)
        features['events_per_day'] = len(player_events) / max(tenure_days, 1)

        sessions = self.session_detector.detect_sessions(player_events)
        if sessions:
            features['events_per_session'] = len(player_events) / len(sessions)
        else:
            features['events_per_session'] = 0

        # Intensity over time (trend analysis)
        daily_events = self._group_events_by_day(player_events)
        daily_counts = [len(events) for events in daily_events.values()]

        if len(daily_counts) > 1:
            # Linear regression slope (intensity trend)
            x = np.arange(len(daily_counts))
            y = np.array(daily_counts)
            slope = np.polyfit(x, y, 1)[0]
            features['intensity_trend'] = slope  # Positive = ramping, negative = declining

            # Variance
            features['intensity_variance'] = statistics.variance(daily_counts)
            features['intensity_cv'] = statistics.stdev(daily_counts) / statistics.mean(daily_counts) if statistics.mean(daily_counts) > 0 else 0
        else:
            features['intensity_trend'] = 0
            features['intensity_variance'] = 0
            features['intensity_cv'] = 0

        # Recent vs historical intensity (last 7 days vs prior)
        cutoff_date = last_event - timedelta(days=7)
        recent_events = [e for e in player_events if e['timestamp'] >= cutoff_date]
        historical_events = [e for e in player_events if e['timestamp'] < cutoff_date]

        recent_intensity = len(recent_events) / 7  # Events per day in last week
        if historical_events:
            historical_days = (cutoff_date - first_event).days
            historical_intensity = len(historical_events) / max(historical_days, 1)
        else:
            historical_intensity = recent_intensity

        features['recent_intensity'] = recent_intensity
        features['historical_intensity'] = historical_intensity
        features['intensity_ratio'] = recent_intensity / historical_intensity if historical_intensity > 0 else 1.0

        return features


    def extract_progression_features(
        self,
        player_events: List[Dict[str, Any]],
        all_event_types: List[str]
    ) -> Dict[str, float]:
        """
        Extract progression velocity features.

        Captures HOW they progress through content without hardcoding
        "rusher" or "completionist". Clustering discovers patterns.

        Features:
            - Event diversity (exploration vs focused)
            - Repetition patterns
            - Milestone velocity (if milestone events detected)
        """
        if not player_events:
            return {}

        features = {}

        # Event diversity
        unique_event_types = len(set(e['event_type'] for e in player_events))
        features['unique_event_types'] = unique_event_types
        features['event_type_coverage'] = unique_event_types / max(len(all_event_types), 1)

        # Diversity entropy (same as feature_engagement but relevant here too)
        event_type_counts = Counter(e['event_type'] for e in player_events)
        probabilities = [count / len(player_events) for count in event_type_counts.values()]
        entropy = -sum(p * np.log2(p) for p in probabilities if p > 0)
        max_entropy = np.log2(len(all_event_types)) if len(all_event_types) > 0 else 1
        features['exploration_entropy'] = entropy / max_entropy if max_entropy > 0 else 0

        # Repetition vs exploration
        most_common_event_type, most_common_count = event_type_counts.most_common(1)[0]
        features['repeat_event_ratio'] = most_common_count / len(player_events)
        features['exploration_breadth'] = 1.0 - features['repeat_event_ratio']

        # Event discovery velocity (how fast they try new event types)
        sorted_events = sorted(player_events, key=lambda e: e['timestamp'])
        seen_types = set()
        discovery_times = []

        for i, event in enumerate(sorted_events):
            if event['event_type'] not in seen_types:
                seen_types.add(event['event_type'])
                discovery_times.append(i)  # Event index when new type discovered

        if len(discovery_times) > 1:
            # Rate of discovery (slope of cumulative new types over time)
            x = np.arange(len(discovery_times))
            y = np.array(discovery_times)
            features['discovery_velocity'] = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0
        else:
            features['discovery_velocity'] = 0

        # Time to discover all event types they'll ever use
        first_event_time = sorted_events[0]['timestamp']
        last_discovery_time = sorted_events[discovery_times[-1]]['timestamp'] if discovery_times else first_event_time
        discovery_period_days = (last_discovery_time - first_event_time).days + 1
        features['discovery_period_days'] = discovery_period_days

        return features


    def extract_content_consumption_features(
        self,
        player_events: List[Dict[str, Any]],
        all_event_types: List[str]
    ) -> Dict[str, float]:
        """
        Extract content consumption velocity features.

        Captures how fast they consume available content.
        Different from progression - this is about content exhaustion risk.

        Features:
            - Content coverage (% of available content consumed)
            - Consumption velocity (rate of content consumption)
            - Replay behavior (revisit old content vs only new)
        """
        if not player_events:
            return {}

        features = {}

        # Content coverage (proxy: unique event types used / available)
        unique_event_types = len(set(e['event_type'] for e in player_events))
        features['content_coverage'] = unique_event_types / max(len(all_event_types), 1)

        # Consumption velocity (how fast they reach high coverage)
        sorted_events = sorted(player_events, key=lambda e: e['timestamp'])
        first_event = sorted_events[0]['timestamp']
        last_event = sorted_events[-1]['timestamp']
        tenure_days = (last_event - first_event).days + 1

        features['content_coverage_velocity'] = features['content_coverage'] / max(tenure_days, 1)

        # Replay behavior (how often they repeat same event types)
        total_events = len(player_events)
        unique_events = unique_event_types
        features['replay_ratio'] = (total_events - unique_events) / max(total_events, 1)

        # Depth vs breadth
        # Depth: focus on few event types (high repeat ratio)
        # Breadth: sample many event types (high coverage, low repeat)
        features['depth_focus'] = features['replay_ratio']
        features['breadth_focus'] = features['content_coverage']

        # Content exhaustion risk (high coverage + low tenure = fast consumption)
        # FIX: Use configurable thresholds instead of hard-coded values
        if tenure_days < self.exhaustion_tenure_threshold and \
           features['content_coverage'] > self.exhaustion_coverage_high:
            features['exhaustion_risk'] = 1.0
        elif tenure_days < (self.exhaustion_tenure_threshold * 2) and \
             features['content_coverage'] > self.exhaustion_coverage_very_high:
            features['exhaustion_risk'] = 0.7
        elif features['content_coverage'] > self.exhaustion_coverage_complete:
            features['exhaustion_risk'] = 0.5
        else:
            features['exhaustion_risk'] = 0.0

        return features


    def extract_learning_curve_features(
        self,
        player_events: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Extract learning curve features.

        Captures how quickly they master the product.
        Uses event diversity over time as proxy for learning.

        Features:
            - Early vs late event diversity
            - Learning velocity (rate of feature adoption)
            - Time to competency markers
        """
        if not player_events:
            return {}

        features = {}
        sorted_events = sorted(player_events, key=lambda e: e['timestamp'])

        # Split into early (first 25%) and late (last 25%) periods
        quarter = len(sorted_events) // 4
        if quarter < 1:
            quarter = 1

        early_events = sorted_events[:quarter]
        late_events = sorted_events[-quarter:]

        # Event diversity in each period
        early_diversity = len(set(e['event_type'] for e in early_events))
        late_diversity = len(set(e['event_type'] for e in late_events))

        features['early_diversity'] = early_diversity
        features['late_diversity'] = late_diversity
        features['diversity_growth'] = late_diversity - early_diversity
        features['diversity_growth_ratio'] = late_diversity / max(early_diversity, 1)

        # Learning velocity (how fast they discover new event types)
        # Already calculated in progression_features, but relevant here
        seen_types = set()
        first_occurrences = []

        for i, event in enumerate(sorted_events):
            if event['event_type'] not in seen_types:
                seen_types.add(event['event_type'])
                time_since_start = (event['timestamp'] - sorted_events[0]['timestamp']).total_seconds() / 3600  # Hours
                first_occurrences.append(time_since_start)

        if len(first_occurrences) > 1:
            # Average time between discovering new event types
            time_diffs = [first_occurrences[i+1] - first_occurrences[i] for i in range(len(first_occurrences)-1)]
            features['avg_time_between_discoveries_hours'] = statistics.mean(time_diffs)

            # Learning acceleration (are discoveries speeding up or slowing down?)
            if len(time_diffs) > 2:
                early_discovery_rate = statistics.mean(time_diffs[:len(time_diffs)//2])
                late_discovery_rate = statistics.mean(time_diffs[len(time_diffs)//2:])
                features['learning_acceleration'] = early_discovery_rate / max(late_discovery_rate, 1)
                # > 1.0 = slowing down (learning curve flattening)
                # < 1.0 = speeding up (still discovering rapidly)
            else:
                features['learning_acceleration'] = 1.0
        else:
            features['avg_time_between_discoveries_hours'] = 0
            features['learning_acceleration'] = 1.0

        # Time to "competency" (proxy: used 50% of available event types)
        half_types = len(set(e['event_type'] for e in sorted_events)) / 2
        events_to_half = 0
        seen = set()
        for i, event in enumerate(sorted_events):
            seen.add(event['event_type'])
            if len(seen) >= half_types:
                events_to_half = i + 1
                break

        features['events_to_half_coverage'] = events_to_half
        features['learning_efficiency'] = len(set(e['event_type'] for e in sorted_events)) / max(len(sorted_events), 1)

        return features


    def extract_volatility_features(
        self,
        player_events: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Extract volatility/stability features.

        Captures how consistent their behavior is over time.

        Features:
            - Session length variance
            - Session frequency variance
            - Event type distribution stability
            - Behavioral predictability
        """
        if not player_events:
            return {}

        features = {}
        sessions = self.session_detector.detect_sessions(player_events)

        # Session length volatility
        if len(sessions) > 1:
            session_lengths = [s.duration_minutes for s in sessions]
            features['session_length_mean'] = statistics.mean(session_lengths)
            features['session_length_variance'] = statistics.variance(session_lengths)
            features['session_length_cv'] = statistics.stdev(session_lengths) / statistics.mean(session_lengths) if statistics.mean(session_lengths) > 0 else 0
        else:
            features['session_length_mean'] = sessions[0].duration_minutes if sessions else 0
            features['session_length_variance'] = 0
            features['session_length_cv'] = 0

        # Session frequency volatility
        if len(sessions) > 2:
            inter_session_gaps = []
            for i in range(1, len(sessions)):
                gap_hours = (sessions[i].start_time - sessions[i-1].end_time).total_seconds() / 3600
                inter_session_gaps.append(gap_hours)

            features['session_gap_mean'] = statistics.mean(inter_session_gaps)
            features['session_gap_variance'] = statistics.variance(inter_session_gaps)
            features['session_gap_cv'] = statistics.stdev(inter_session_gaps) / statistics.mean(inter_session_gaps) if statistics.mean(inter_session_gaps) > 0 else 0
        else:
            features['session_gap_mean'] = 0
            features['session_gap_variance'] = 0
            features['session_gap_cv'] = 0

        # Event type distribution stability over time
        # Split into thirds, compare distributions
        third = len(player_events) // 3
        if third > 0:
            sorted_events = sorted(player_events, key=lambda e: e['timestamp'])

            first_third = sorted_events[:third]
            second_third = sorted_events[third:2*third]
            last_third = sorted_events[2*third:]

            dist1 = self._event_type_distribution(first_third)
            dist2 = self._event_type_distribution(second_third)
            dist3 = self._event_type_distribution(last_third)

            # KL divergence between distributions (measure of change)
            kl_1_2 = self._kl_divergence(dist1, dist2)
            kl_2_3 = self._kl_divergence(dist2, dist3)

            features['event_distribution_stability'] = 1.0 / (1.0 + (kl_1_2 + kl_2_3) / 2)
            features['event_distribution_volatility'] = (kl_1_2 + kl_2_3) / 2
        else:
            features['event_distribution_stability'] = 1.0
            features['event_distribution_volatility'] = 0.0

        # Overall predictability score (inverse of average CV)
        cv_features = [
            features.get('session_length_cv', 0),
            features.get('session_gap_cv', 0),
            features.get('event_distribution_volatility', 0)
        ]
        avg_cv = statistics.mean(cv_features)
        features['predictability_score'] = 1.0 / (1.0 + avg_cv)
        features['volatility_score'] = avg_cv

        return features


    def extract_purchase_timing_features(
        self,
        player_events: List[Dict[str, Any]],
        game_launch_date: datetime
    ) -> Dict[str, float]:
        """
        Extract purchase timing features.

        Uses first event as proxy for purchase date.
        Captures when they bought relative to launch.

        Features:
            - Days after launch
            - Launch window indicators
        """
        if not player_events:
            return {}

        features = {}

        # First play as proxy for purchase
        first_play = min(e['timestamp'] for e in player_events)

        # Make game_launch_date timezone-aware if first_play is
        if first_play.tzinfo is not None and game_launch_date.tzinfo is None:
            from datetime import timezone
            game_launch_date = game_launch_date.replace(tzinfo=timezone.utc)

        days_after_launch = (first_play - game_launch_date).days

        features['days_after_launch'] = max(days_after_launch, 0)
        features['is_launch_week'] = 1.0 if days_after_launch <= 7 else 0.0
        features['is_launch_month'] = 1.0 if days_after_launch <= 30 else 0.0
        features['is_first_quarter'] = 1.0 if days_after_launch <= 90 else 0.0

        # Categorization helpers
        if days_after_launch <= 7:
            features['launch_category'] = 0  # Launch buyer
        elif days_after_launch <= 90:
            features['launch_category'] = 1  # Early adopter
        elif days_after_launch <= 180:
            features['launch_category'] = 2  # Patient gamer
        else:
            features['launch_category'] = 3  # Late adopter

        return features


    # Helper methods

    def _calculate_streaks(self, play_dates: List[datetime.date]) -> List[int]:
        """Calculate consecutive day play streaks"""
        if not play_dates:
            return []

        streaks = []
        current_streak = 1

        for i in range(1, len(play_dates)):
            if (play_dates[i] - play_dates[i-1]).days == 1:
                current_streak += 1
            else:
                streaks.append(current_streak)
                current_streak = 1

        streaks.append(current_streak)
        return streaks


    def _group_events_by_day(self, player_events: List[Dict[str, Any]]) -> Dict[datetime.date, List[Dict[str, Any]]]:
        """Group events by calendar day"""
        daily_events = defaultdict(list)
        for event in player_events:
            day = event['timestamp'].date()
            daily_events[day].append(event)
        return daily_events


    def _event_type_distribution(self, events: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate event type probability distribution"""
        if not events:
            return {}

        counts = Counter(e['event_type'] for e in events)
        total = len(events)
        return {event_type: count / total for event_type, count in counts.items()}


    def _kl_divergence(self, dist1: Dict[str, float], dist2: Dict[str, float]) -> float:
        """
        Calculate KL divergence between two probability distributions.
        Measures how much dist1 differs from dist2.
        """
        if not dist1 or not dist2:
            return 0.0

        # Get all event types from both distributions
        all_types = set(dist1.keys()) | set(dist2.keys())

        kl = 0.0
        for event_type in all_types:
            p = dist1.get(event_type, 1e-10)  # Small value to avoid log(0)
            q = dist2.get(event_type, 1e-10)
            kl += p * np.log2(p / q)

        return max(kl, 0.0)  # KL divergence is non-negative
