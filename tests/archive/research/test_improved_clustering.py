#!/usr/bin/env python3
"""
Test improved clustering on real customer data.

Validates that the new clustering produces balanced, descriptive segments
instead of "everyone vs outliers".
"""

import asyncio
import sys
import os
import numpy as np

os.environ["DATABASE_URL"] = "postgresql://postgres:XzLuopeMhZwurhlOWaObisBJxiTFViCb@turntable.proxy.rlwy.net:30126/railway"

sys.path.insert(0, os.path.dirname(__file__))

from backend.core.database import get_db_session
from backend.segmentation.clustering_improvements import (
    ImprovedClusteringEngine,
    ClusteringConfig,
    generate_clustering_quality_report
)
from backend.segmentation.fraud_anomaly_detector import (
    FraudAnomalyDetector,
    generate_anomaly_report
)
from sqlalchemy import text


async def get_customer_features_for_testing(limit=1000):
    """Get real customer features from database"""
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    customer_id,
                    total_orders,
                    lifetime_value,
                    days_since_last_purchase,
                    customer_tenure_days
                FROM platform.customer_profiles
                WHERE total_orders > 0
                    AND lifetime_value > 0
                ORDER BY RANDOM()
                LIMIT :limit
            """),
            {"limit": limit}
        )

        customers = []
        for row in result:
            customers.append({
                'customer_id': row.customer_id,
                'total_orders': row.total_orders,
                'lifetime_value': float(row.lifetime_value),
                'days_since_last_purchase': row.days_since_last_purchase,
                'tenure_days': row.customer_tenure_days
            })

        return customers


async def test_improved_clustering():
    """Test that improved clustering produces balanced segments"""
    print("\n" + "=" * 70)
    print("TEST: IMPROVED CLUSTERING ALGORITHM")
    print("=" * 70)

    # Load sample data
    print("\n📥 Loading sample customers...")
    customers = await get_customer_features_for_testing(limit=1000)
    print(f"✅ Loaded {len(customers)} customers")

    # Test purchase_frequency axis (orders)
    print("\n🧮 Testing purchase_frequency clustering...")

    # Extract features
    features = np.array([[c['total_orders']] for c in customers])

    print(f"   Feature range: {features.min():.0f} to {features.max():.0f} orders")
    print(f"   Feature mean: {features.mean():.1f} ± {features.std():.1f}")

    # Test with different configurations
    configs_to_test = [
        ("DEFAULT (k=3-8, max_dominant=50%)", ClusteringConfig()),
        ("STRICT (k=4-8, max_dominant=40%)", ClusteringConfig(min_k=4, max_k=8, max_dominant_segment_pct=40.0)),
        ("RELAXED (k=3-6, max_dominant=60%)", ClusteringConfig(min_k=3, max_k=6, max_dominant_segment_pct=60.0)),
    ]

    for config_name, config in configs_to_test:
        print(f"\n--- Testing: {config_name} ---")

        engine = ImprovedClusteringEngine(config)

        labels, kmeans, metrics = engine.cluster_with_quality_validation(
            features,
            "purchase_frequency"
        )

        print(f"   k={metrics.k}")
        print(f"   Silhouette: {metrics.silhouette_score:.3f}")
        print(f"   Largest segment: {metrics.largest_segment_pct:.1f}%")
        print(f"   Smallest segment: {metrics.smallest_segment_pct:.1f}%")
        print(f"   Segment sizes: {metrics.segment_sizes}")
        print(f"   Balanced: {'✅ YES' if metrics.is_balanced else '❌ NO'}")
        print(f"   Descriptive: {'✅ YES' if metrics.is_descriptive else '❌ NO'}")

        if metrics.passes_quality_check:
            print(f"   🎉 QUALITY CHECK: ✅ PASS")
        else:
            print(f"   ⚠️  QUALITY CHECK: FAIL")


async def test_fraud_detection():
    """Test fraud and anomaly detection"""
    print("\n" + "=" * 70)
    print("TEST: FRAUD & ANOMALY DETECTION")
    print("=" * 70)

    # Load sample data
    print("\n📥 Loading sample customers...")
    customers = await get_customer_features_for_testing(limit=500)

    # Calculate population stats
    all_values = np.array([c['lifetime_value'] for c in customers])
    tenures = np.array([c['tenure_days'] for c in customers if c['tenure_days']])

    population_stats = {
        'all_values': all_values,
        'velocity_mean': 0.1,  # Placeholder
        'velocity_std': 0.05
    }

    # Initialize detector
    detector = FraudAnomalyDetector()

    # Test on sample
    print("\n🔍 Analyzing customers for anomalies...")

    all_anomalies = []
    all_fraud = []

    for customer in customers[:100]:  # Test on 100 customers
        customer_data = {
            'total_orders': customer['total_orders'],
            'lifetime_value': customer['lifetime_value'],
            'return_count': max(0, int(customer['total_orders'] * np.random.uniform(0, 0.3))),  # Simulated
            'orders_per_day': customer['total_orders'] / max(customer['tenure_days'], 1) if customer['tenure_days'] else 0,
            'recent_value': customer['lifetime_value'] * 0.3,  # Simulated
            'historical_avg': customer['lifetime_value'] * 0.7 / max(customer['total_orders'], 1)
        }

        anomalies, fraud = detector.analyze_customer_for_anomalies(
            customer['customer_id'],
            customer_data,
            population_stats
        )

        if anomalies:
            all_anomalies.extend(anomalies)
        if fraud:
            all_fraud.append(fraud)

    print(f"\n✅ Analysis complete:")
    print(f"   Total anomalies detected: {len(all_anomalies)}")
    print(f"   Fraud cases flagged: {sum(1 for f in all_fraud if f.should_flag_for_review)}")

    # Show breakdown
    from collections import Counter
    anomaly_types = Counter([a.anomaly_type for a in all_anomalies])
    print(f"\n   Anomalies by type:")
    for anom_type, count in anomaly_types.most_common():
        print(f"     {anom_type.value}: {count}")

    # Show top VIPs
    vip_anomalies = [a for a in all_anomalies if a.anomaly_type.value == "vip_customer"]
    if vip_anomalies:
        print(f"\n   🌟 VIP customers detected: {len(vip_anomalies)}")
        for vip in vip_anomalies[:3]:
            print(f"     {vip.customer_id}: {vip.description}")

    # Show fraud flags
    fraud_flags = [f for f in all_fraud if f.should_flag_for_review]
    if fraud_flags:
        print(f"\n   ⚠️  Fraud flags: {len(fraud_flags)}")
        for fraud in fraud_flags[:3]:
            print(f"     {fraud.customer_id}: score={fraud.fraud_score:.2f}, indicators={fraud.indicators}")


async def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("CLUSTERING IMPROVEMENTS VALIDATION")
    print("=" * 70)
    print("\nGoal: Verify clustering produces balanced, descriptive segments")
    print("Success criteria:")
    print("  - No segment > 50% of population")
    print("  - No segment < 3% of population")
    print("  - Silhouette score >= 0.35")
    print("  - Fraud detection working")

    # Test 1: Improved clustering
    await test_improved_clustering()

    # Test 2: Fraud detection
    await test_fraud_detection()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\n✅ Tests complete! Review results above.")
    print("\nNext steps:")
    print("  1. If quality checks pass → integrate into ecommerce_clustering_engine.py")
    print("  2. If fraud detection works → add to customer profile pipeline")
    print("  3. Re-run clustering on full dataset")
    print("  4. Deploy improved algorithm")


if __name__ == "__main__":
    asyncio.run(main())
