"""
E-Commerce Multi-Axis Behavioral Segmentation

This module provides clustering and feature extraction for discovering
customer behavioral segments across 14 independent dimensions.

Main components:
- EcommerceClusteringEngine: Discovers segments via KMeans clustering
- EcommerceFeatureExtractor: Extracts features from order history
- AI segment naming: Claude API integration for human-readable names

Usage:
    from backend.segmentation import EcommerceClusteringEngine

    engine = EcommerceClusteringEngine(
        anthropic_api_key=os.getenv('ANTHROPIC_API_KEY')
    )

    # Discover segments
    segments = await engine.discover_multi_axis_segments('linda_quilting')

    # Calculate customer profile
    profile = await engine.calculate_customer_profile(
        'C12345',
        'linda_quilting'
    )
"""

from backend.segmentation.ecommerce_clustering_engine import (
    EcommerceClusteringEngine,
    DiscoveredSegment,
    CustomerAxisProfile,
    CustomerMultiAxisProfile
)

from backend.segmentation.ecommerce_feature_extraction import (
    EcommerceFeatureExtractor
)

__all__ = [
    'EcommerceClusteringEngine',
    'EcommerceFeatureExtractor',
    'DiscoveredSegment',
    'CustomerAxisProfile',
    'CustomerMultiAxisProfile'
]

__version__ = '1.0.0'
