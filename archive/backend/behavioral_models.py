"""
Behavioral Models for Unified Segmentation System

Minimal models needed for taxonomy calibration and categorization.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class PlayerBehaviorEvent:
    """Individual behavioral event for a player."""
    player_id: str
    game_id: str
    event_type: str
    event_timestamp: datetime
    event_data: Dict

    # Behavioral metrics
    session_duration: Optional[float] = None
    monetary_value: Optional[float] = None
    engagement_score: Optional[float] = None


@dataclass
class PlayerBehavioralData:
    """Aggregated behavioral data for a player."""
    player_id: str
    game_id: str

    # Monetization metrics
    monthly_spend: float = 0.0
    purchase_frequency: float = 0.0
    avg_purchase_amount: float = 0.0

    # Engagement metrics
    avg_daily_sessions: float = 0.0
    avg_session_duration: float = 0.0
    play_day_frequency: float = 0.0

    # Temporal metrics
    weekend_vs_weekday_ratio: float = 1.0
    session_consistency: float = 0.0

    # Social metrics
    guild_participation: float = 0.0
    social_feature_usage: float = 0.0

    # Metadata
    total_events: int = 0
    days_active: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
