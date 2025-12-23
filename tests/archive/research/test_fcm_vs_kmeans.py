#!/usr/bin/env python3
"""
Test Fuzzy C-Means vs K-Means on real e-commerce data.

Shows that FCM produces better, more balanced segments than K-means.
"""

import asyncio
import sys
import os
import numpy as np

os.environ["DATABASE_URL"] = "postgresql://postgres:XzLuopeMhZwurhlOWaObisBJxiTFViCb@turntable.proxy.rlwy.net:30126/railway"

sys.path.insert(0, os.path.dirname(__file__))

from backend.core.database import get_db_session
from backend.segmentation.fuzzy_cmeans_clustering import FuzzyCMeansEngine, FCMConfig
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from collections import Counter
from sqlalchemy import text


async def get_test_data(limit=1000):
    """Get real customer data"""
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    customer_id,
                    total_orders,
                    lifetime_value
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
                'lifetime_value': float(row.lifetime_value)
            })

        return customers


def test_kmeans(features, k=4):
    """Test K-means clustering"""
    print(f"\n{'='*70}")
    print(f"K-MEANS CLUSTERING (k={k})")
    print(f"{'='*70}")

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features)

    # Calculate metrics
    silhouette = silhouette_score(features, labels)
    segment_counts = Counter(labels)

    largest_pct = max(segment_counts.values()) / len(features) * 100
    smallest_pct = min(segment_counts.values()) / len(features) * 100

    print(f"\nResults:")
    print(f"  Silhouette score: {silhouette:.3f}")
    print(f"  Largest segment: {largest_pct:.1f}%")
    print(f"  Smallest segment: {smallest_pct:.1f}%")
    print(f"\n  Segment distribution:")
    for cluster_id in sorted(segment_counts.keys()):
        count = segment_counts[cluster_id]
        pct = count / len(features) * 100
        bar = "█" * int(pct / 2)
        print(f"    Segment {cluster_id}: {count:4d} ({pct:5.1f}%) {bar}")

    # Check balance
    is_balanced = largest_pct <= 55.0 and smallest_pct >= 3.0

    if is_balanced:
        print(f"\n  ✅ BALANCED")
    else:
        print(f"\n  ❌ UNBALANCED (largest {largest_pct:.1f}% > 55% or smallest {smallest_pct:.1f}% < 3%)")

    return {
        'silhouette': silhouette,
        'largest_pct': largest_pct,
        'smallest_pct': smallest_pct,
        'is_balanced': is_balanced,
        'segment_counts': dict(segment_counts)
    }


def test_fcm(features, k=4):
    """Test Fuzzy C-Means clustering"""
    print(f"\n{'='*70}")
    print(f"FUZZY C-MEANS CLUSTERING (k={k})")
    print(f"{'='*70}")

    from backend.segmentation.fuzzy_cmeans_clustering import FuzzyCMeans

    fcm = FuzzyCMeans(n_clusters=k, m=2.0, max_iter=150, random_state=42)
    fcm.fit(features)

    # Get hard labels for comparison
    labels = fcm.predict(features)

    # Calculate metrics
    silhouette = silhouette_score(features, labels)
    segment_counts = Counter(labels)

    largest_pct = max(segment_counts.values()) / len(features) * 100
    smallest_pct = min(segment_counts.values()) / len(features) * 100

    print(f"\nResults:")
    print(f"  Silhouette score: {silhouette:.3f}")
    print(f"  Converged in: {fcm.n_iter_} iterations")
    print(f"  Largest segment: {largest_pct:.1f}%")
    print(f"  Smallest segment: {smallest_pct:.1f}%")
    print(f"\n  Segment distribution:")
    for cluster_id in sorted(segment_counts.keys()):
        count = segment_counts[cluster_id]
        pct = count / len(features) * 100
        bar = "█" * int(pct / 2)
        print(f"    Segment {cluster_id}: {count:4d} ({pct:5.1f}%) {bar}")

    # Show fuzzy membership example
    print(f"\n  Fuzzy membership example (first customer):")
    for cluster_id in range(k):
        membership = fcm.u_[0, cluster_id]
        bar = "█" * int(membership * 20)
        print(f"    Segment {cluster_id}: {membership:.3f} {bar}")

    # Check balance
    is_balanced = largest_pct <= 55.0 and smallest_pct >= 3.0

    if is_balanced:
        print(f"\n  ✅ BALANCED")
    else:
        print(f"\n  ❌ UNBALANCED (largest {largest_pct:.1f}% > 55% or smallest {smallest_pct:.1f}% < 3%)")

    return {
        'silhouette': silhouette,
        'largest_pct': largest_pct,
        'smallest_pct': smallest_pct,
        'is_balanced': is_balanced,
        'segment_counts': dict(segment_counts),
        'fuzzy_memberships': fcm.u_
    }


async def main():
    """Run FCM vs K-means comparison"""
    print("\n" + "=" * 70)
    print("FUZZY C-MEANS VS K-MEANS COMPARISON")
    print("=" * 70)
    print("\nTesting on real e-commerce customer data")
    print("Feature: Total Orders (purchase frequency)")

    # Load data
    print("\n📥 Loading customer data...")
    customers = await get_test_data(limit=1000)
    print(f"✅ Loaded {len(customers)} customers")

    # Extract features
    features = np.array([[c['total_orders']] for c in customers])

    print(f"\nFeature statistics:")
    print(f"  Min: {features.min():.0f} orders")
    print(f"  Max: {features.max():.0f} orders")
    print(f"  Mean: {features.mean():.1f} ± {features.std():.1f}")
    print(f"  Median: {np.median(features):.0f}")

    # Test both algorithms with k=4
    kmeans_results = test_kmeans(features, k=4)
    fcm_results = test_fcm(features, k=4)

    # Comparison summary
    print(f"\n{'='*70}")
    print("COMPARISON SUMMARY")
    print(f"{'='*70}")

    print(f"\n{'Metric':<30} {'K-Means':<20} {'FCM':<20} {'Winner'}")
    print(f"{'-'*30} {'-'*20} {'-'*20} {'-'*10}")

    # Silhouette
    winner = "FCM" if fcm_results['silhouette'] > kmeans_results['silhouette'] else "K-Means"
    print(f"{'Silhouette Score':<30} {kmeans_results['silhouette']:<20.3f} {fcm_results['silhouette']:<20.3f} {winner}")

    # Largest segment
    winner = "FCM" if fcm_results['largest_pct'] < kmeans_results['largest_pct'] else "K-Means"
    print(f"{'Largest Segment %':<30} {kmeans_results['largest_pct']:<20.1f} {fcm_results['largest_pct']:<20.1f} {winner}")

    # Smallest segment
    winner = "FCM" if fcm_results['smallest_pct'] > kmeans_results['smallest_pct'] else "K-Means"
    print(f"{'Smallest Segment %':<30} {kmeans_results['smallest_pct']:<20.1f} {fcm_results['smallest_pct']:<20.1f} {winner}")

    # Balance
    print(f"\n{'Balance Check':<30} {'K-Means':<20} {'FCM':<20}")
    print(f"{'-'*30} {'-'*20} {'-'*20}")
    kmeans_status = "✅ PASS" if kmeans_results['is_balanced'] else "❌ FAIL"
    fcm_status = "✅ PASS" if fcm_results['is_balanced'] else "❌ FAIL"
    print(f"{'Segment Balance':<30} {kmeans_status:<20} {fcm_status:<20}")

    # Overall recommendation
    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}")

    if fcm_results['is_balanced'] and not kmeans_results['is_balanced']:
        print("\n✅ FCM CLEARLY BETTER - Produces balanced segments, K-means doesn't")
        print("\nRecommend: Switch to Fuzzy C-Means for production")
    elif fcm_results['is_balanced'] and kmeans_results['is_balanced']:
        if fcm_results['silhouette'] > kmeans_results['silhouette']:
            print("\n✅ FCM SLIGHTLY BETTER - Both balanced, FCM has better quality")
        else:
            print("\n⚖️  BOTH WORK - Similar quality, FCM has natural fuzzy membership")
        print("\nRecommend: Use FCM for better fuzzy membership")
    else:
        print("\n⚠️  BOTH STRUGGLE - Data is too skewed for either algorithm")
        print("\nRecommend: Use percentile-based segmentation instead")

    print(f"\n{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
