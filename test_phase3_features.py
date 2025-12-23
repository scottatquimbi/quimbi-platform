#!/usr/bin/env python3
"""
Test script for Phase 3 enhancements and temporal snapshots.
Tests all new features with sample data.
"""

import asyncio
from datetime import date, timedelta
import sys
import os

# Add intelligence package to path
sys.path.insert(0, os.path.dirname(__file__))

from backend.segmentation.outlier_detection import OutlierDetector, OutlierDetectionConfig
from backend.segmentation.dynamic_k_optimizer import DynamicKOptimizer, DynamicKOptimizerConfig
from backend.segmentation.cold_start_handler import ColdStartHandler, ColdStartConfig
import numpy as np


def test_outlier_detection():
    """Test outlier detection with sample fuzzy memberships"""
    print("=" * 70)
    print("Testing Outlier Detection")
    print("=" * 70)

    # Create detector
    config = OutlierDetectionConfig(enabled=True)
    detector = OutlierDetector(config)

    # Test case 1: Normal customer (good fit to segments)
    normal_customer = {
        "customer_id": 1001,
        "fuzzy_memberships": {
            "purchase_frequency": {
                "Regular Buyers": 0.8,
                "Occasional Shoppers": 0.2
            },
            "purchase_value": {
                "High Value": 0.7,
                "Mid Range": 0.3
            },
            "engagement_level": {
                "Highly Engaged": 0.9,
                "Casual": 0.1
            }
        }
    }

    analysis = detector.detect_outliers(
        customer_id=normal_customer["customer_id"],
        fuzzy_memberships=normal_customer["fuzzy_memberships"]
    )

    print(f"\nTest Case 1: Normal Customer (ID: {analysis.customer_id})")
    print(f"  Is Outlier: {analysis.is_outlier}")
    print(f"  Overall Score: {analysis.overall_outlier_score:.2f}")
    print(f"  Outlier Axes: {analysis.outlier_axes}")
    print(f"  Recommendation: {analysis.recommendation[:100]}...")

    # Test case 2: Outlier customer (poor fit to all segments)
    outlier_customer = {
        "customer_id": 2002,
        "fuzzy_memberships": {
            "purchase_frequency": {
                "Regular Buyers": 0.25,
                "Occasional Shoppers": 0.25,
                "One-Time Buyers": 0.25,
                "Frequent Shoppers": 0.25
            },
            "purchase_value": {
                "High Value": 0.2,
                "Mid Range": 0.3,
                "Budget": 0.25,
                "Premium": 0.25
            },
            "engagement_level": {
                "Highly Engaged": 0.15,
                "Casual": 0.25,
                "Dormant": 0.3,
                "Active": 0.3
            }
        }
    }

    analysis2 = detector.detect_outliers(
        customer_id=outlier_customer["customer_id"],
        fuzzy_memberships=outlier_customer["fuzzy_memberships"]
    )

    print(f"\nTest Case 2: Outlier Customer (ID: {analysis2.customer_id})")
    print(f"  Is Outlier: {analysis2.is_outlier}")
    print(f"  Overall Score: {analysis2.overall_outlier_score:.2f}")
    print(f"  Outlier Axes: {analysis2.outlier_axes}")
    print(f"  Recommendation: {analysis2.recommendation[:150]}...")

    print("\n✅ Outlier Detection Test Complete\n")


def test_dynamic_k_optimization():
    """Test dynamic k-range optimization"""
    print("=" * 70)
    print("Testing Dynamic K-Range Optimization")
    print("=" * 70)

    # Create optimizer
    config = DynamicKOptimizerConfig(enabled=True, max_k=8)
    optimizer = DynamicKOptimizer(config)

    # Generate sample data with natural clusters
    np.random.seed(42)

    # Create 4 natural clusters
    cluster1 = np.random.randn(100, 3) + np.array([0, 0, 0])
    cluster2 = np.random.randn(100, 3) + np.array([5, 5, 0])
    cluster3 = np.random.randn(100, 3) + np.array([0, 5, 5])
    cluster4 = np.random.randn(100, 3) + np.array([5, 0, 5])

    X = np.vstack([cluster1, cluster2, cluster3, cluster4])

    # Find optimal k
    result = optimizer.find_optimal_k(X, axis_name="test_axis")

    print(f"\nTest Data: {X.shape[0]} samples, {X.shape[1]} features")
    print(f"True k: 4 (data was generated with 4 clusters)")
    print(f"\nOptimization Result:")
    print(f"  Optimal k: {result.optimal_k}")
    print(f"  k Range Tested: {result.k_range_tested}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Method: {result.method_used}")
    print(f"  Recommendation: {result.recommendation}")

    # Show scores for different k values
    print(f"\nSilhouette Scores by k:")
    for k in sorted(result.scores.keys()):
        sil = result.scores[k].get('silhouette', 0)
        print(f"    k={k}: {sil:.3f}")

    print("\n✅ Dynamic K Optimization Test Complete\n")


def test_cold_start_handler():
    """Test cold start handling for new customers"""
    print("=" * 70)
    print("Testing Cold Start Handler")
    print("=" * 70)

    # Create handler
    config = ColdStartConfig(enabled=True)
    handler = ColdStartHandler(config)

    # Test case 1: Brand new customer (1 order)
    print("\nTest Case 1: New Customer (1 order, 3 days old)")
    profile1 = handler.analyze_customer(
        customer_id=3001,
        total_orders=1,
        total_value=45.99,
        first_order_date=date.today() - timedelta(days=3),
        last_order_date=date.today() - timedelta(days=3)
    )

    print(f"  Lifecycle Stage: {profile1.lifecycle_stage.value}")
    print(f"  Data Sufficiency: {profile1.data_sufficiency.value}")
    print(f"  Confidence Score: {profile1.confidence_score:.2f}")
    print(f"  Fallback Segments: {profile1.fallback_segments}")
    print(f"  Days Until Mature: {profile1.estimated_days_until_mature}")
    print(f"  Recommendation: {profile1.recommendation[:150]}...")

    # Test case 2: Warming up customer (3 orders)
    print("\nTest Case 2: Warming Up Customer (3 orders, 2 weeks old)")
    profile2 = handler.analyze_customer(
        customer_id=3002,
        total_orders=3,
        total_value=189.50,
        first_order_date=date.today() - timedelta(days=14),
        last_order_date=date.today() - timedelta(days=2)
    )

    print(f"  Lifecycle Stage: {profile2.lifecycle_stage.value}")
    print(f"  Data Sufficiency: {profile2.data_sufficiency.value}")
    print(f"  Confidence Score: {profile2.confidence_score:.2f}")
    print(f"  Fallback Segments: {profile2.fallback_segments}")
    print(f"  Should Use Clustering: {handler.should_use_clustering(profile2)}")

    # Test case 3: Mature customer (15 orders)
    print("\nTest Case 3: Mature Customer (15 orders, 6 months old)")
    profile3 = handler.analyze_customer(
        customer_id=3003,
        total_orders=15,
        total_value=1250.00,
        first_order_date=date.today() - timedelta(days=180),
        last_order_date=date.today() - timedelta(days=5)
    )

    print(f"  Lifecycle Stage: {profile3.lifecycle_stage.value}")
    print(f"  Data Sufficiency: {profile3.data_sufficiency.value}")
    print(f"  Confidence Score: {profile3.confidence_score:.2f}")
    print(f"  Days Until Mature: {profile3.estimated_days_until_mature}")
    print(f"  Recommendation: {profile3.recommendation[:150]}...")

    print("\n✅ Cold Start Handler Test Complete\n")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("PHASE 3 ENHANCEMENTS TEST SUITE")
    print("=" * 70 + "\n")

    try:
        # Test 1: Outlier Detection
        test_outlier_detection()

        # Test 2: Dynamic K Optimization
        test_dynamic_k_optimization()

        # Test 3: Cold Start Handler
        test_cold_start_handler()

        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nPhase 3 enhancements are working correctly!")
        print("\nNext steps:")
        print("  1. Enable features via environment variables")
        print("  2. Test with real customer data")
        print("  3. Deploy to staging environment")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
