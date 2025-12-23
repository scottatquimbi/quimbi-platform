#!/usr/bin/env python3
"""
Test clustering quality - verify segments are descriptive and meaningful.

This validates that our clustering algorithm produces interpretable segments
that describe the actual customer population, not just "everyone vs outliers".
"""

import asyncio
import os
import sys
import numpy as np
from collections import Counter, defaultdict
from datetime import date, timedelta

# Set environment
os.environ["DATABASE_URL"] = "postgresql://postgres:XzLuopeMhZwurhlOWaObisBJxiTFViCb@turntable.proxy.rlwy.net:30126/railway"

sys.path.insert(0, os.path.dirname(__file__))

from backend.core.database import get_db_session
from sqlalchemy import text


async def get_sample_customers(limit=500):
    """Get sample of customers with their behavioral features"""
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    customer_id,
                    total_orders,
                    total_value,
                    days_since_last_purchase,
                    days_since_first_order,
                    first_order_date,
                    last_order_date,
                    avg_order_value,
                    fuzzy_memberships,
                    dominant_segments
                FROM platform.customer_profiles
                WHERE total_orders > 0
                    AND total_value > 0
                    AND days_since_last_purchase IS NOT NULL
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
                'total_value': float(row.total_value),
                'days_since_last_purchase': row.days_since_last_purchase,
                'days_since_first_order': row.days_since_first_order,
                'first_order_date': row.first_order_date,
                'last_order_date': row.last_order_date,
                'avg_order_value': float(row.avg_order_value) if row.avg_order_value else 0,
                'fuzzy_memberships': row.fuzzy_memberships,
                'dominant_segments': row.dominant_segments
            })

        return customers


def analyze_segment_distribution(customers):
    """Analyze how customers are distributed across segments"""
    print("\n" + "=" * 70)
    print("SEGMENT DISTRIBUTION ANALYSIS")
    print("=" * 70)

    # Count customers per dominant segment (per axis)
    axis_distributions = defaultdict(Counter)

    for customer in customers:
        if customer['dominant_segments']:
            for axis, segment in customer['dominant_segments'].items():
                axis_distributions[axis][segment] += 1

    # Check each axis
    for axis, segment_counts in sorted(axis_distributions.items()):
        print(f"\n📊 {axis.upper()} Axis:")
        print(f"   Total segments: {len(segment_counts)}")

        # Sort by count
        sorted_segments = sorted(segment_counts.items(), key=lambda x: x[1], reverse=True)

        # Check for outlier problem (one huge segment + tiny segments)
        largest_segment_pct = sorted_segments[0][1] / len(customers) * 100

        if largest_segment_pct > 90:
            print(f"   ⚠️  WARNING: Dominant segment has {largest_segment_pct:.1f}% of customers!")
            print(f"   This suggests outlier problem, not descriptive segmentation")

        # Show distribution
        for segment, count in sorted_segments:
            pct = count / len(customers) * 100
            bar = "█" * int(pct / 2)
            print(f"   {segment:30s}: {count:4d} ({pct:5.1f}%) {bar}")


def analyze_fuzzy_membership_quality(customers):
    """Analyze fuzzy membership distributions to detect problems"""
    print("\n" + "=" * 70)
    print("FUZZY MEMBERSHIP QUALITY ANALYSIS")
    print("=" * 70)

    for axis in ['purchase_frequency', 'purchase_value', 'category_exploration', 'price_sensitivity']:
        print(f"\n📈 {axis.upper()}:")

        membership_scores = []
        max_memberships = []
        membership_spreads = []

        for customer in customers:
            if customer['fuzzy_memberships'] and axis in customer['fuzzy_memberships']:
                scores = customer['fuzzy_memberships'][axis]
                if scores:
                    membership_scores.append(scores)
                    max_mem = max(scores.values())
                    max_memberships.append(max_mem)

                    # Spread: difference between top 2 memberships
                    sorted_scores = sorted(scores.values(), reverse=True)
                    if len(sorted_scores) >= 2:
                        spread = sorted_scores[0] - sorted_scores[1]
                        membership_spreads.append(spread)

        if max_memberships:
            avg_max = np.mean(max_memberships)
            print(f"   Avg max membership: {avg_max:.3f}")

            if avg_max < 0.4:
                print(f"   ⚠️  WARNING: Very low max memberships!")
                print(f"   Customers don't fit any cluster well - possible outlier problem")
            elif avg_max > 0.95:
                print(f"   ⚠️  WARNING: Very high max memberships!")
                print(f"   Customers are in hard clusters, not fuzzy - may indicate 2-cluster problem")
            else:
                print(f"   ✅ Good fuzzy membership distribution")

        if membership_spreads:
            avg_spread = np.mean(membership_spreads)
            print(f"   Avg membership spread: {avg_spread:.3f}")

            if avg_spread > 0.8:
                print(f"   ⚠️  WARNING: Very high spread - hard clustering detected")
                print(f"   This suggests 'in group' vs 'out of group' problem")
            elif avg_spread < 0.1:
                print(f"   ⚠️  WARNING: Very low spread - no clear segments")
            else:
                print(f"   ✅ Good membership spread")

        # Show segment count
        unique_segments = set()
        for customer in customers:
            if customer['fuzzy_memberships'] and axis in customer['fuzzy_memberships']:
                unique_segments.update(customer['fuzzy_memberships'][axis].keys())

        print(f"   Segments found: {len(unique_segments)}")
        if len(unique_segments) <= 2:
            print(f"   ⚠️  WARNING: Only {len(unique_segments)} segments on this axis!")
            print(f"   Not enough granularity for meaningful segmentation")


def analyze_segment_characteristics(customers):
    """Analyze what makes each segment unique"""
    print("\n" + "=" * 70)
    print("SEGMENT CHARACTERISTICS ANALYSIS")
    print("=" * 70)

    # Group customers by dominant segment for each axis
    axis = 'purchase_frequency'  # Test with one axis

    if not customers[0].get('dominant_segments'):
        print("⚠️  No dominant segments found in customer data")
        return

    print(f"\n📊 Analyzing {axis.upper()} axis:")

    segment_customers = defaultdict(list)
    for customer in customers:
        if customer['dominant_segments'] and axis in customer['dominant_segments']:
            segment = customer['dominant_segments'][axis]
            segment_customers[segment].append(customer)

    # Analyze each segment
    for segment, seg_customers in sorted(segment_customers.items()):
        if len(seg_customers) < 5:  # Skip tiny segments
            continue

        print(f"\n   Segment: {segment} ({len(seg_customers)} customers)")

        # Calculate statistics
        orders = [c['total_orders'] for c in seg_customers]
        values = [c['total_value'] for c in seg_customers]
        aovs = [c['avg_order_value'] for c in seg_customers]
        recencies = [c['days_since_last_purchase'] for c in seg_customers]

        print(f"      Orders:  {np.mean(orders):.1f} ± {np.std(orders):.1f} (median: {np.median(orders):.0f})")
        print(f"      Value:   ${np.mean(values):.0f} ± ${np.std(values):.0f} (median: ${np.median(values):.0f})")
        print(f"      AOV:     ${np.mean(aovs):.0f} ± ${np.std(aovs):.0f}")
        print(f"      Recency: {np.mean(recencies):.0f} days ± {np.std(recencies):.0f}")

        # Check if segment is actually different from others
        # (This is where we'd detect "everyone vs outliers" problem)


async def test_current_clustering_algorithm():
    """Test what the current clustering algorithm produces"""
    print("\n" + "=" * 70)
    print("CURRENT CLUSTERING ALGORITHM TEST")
    print("=" * 70)

    # Get sample customers
    print("\n🔍 Fetching sample customers from database...")
    customers = await get_sample_customers(limit=500)
    print(f"✅ Loaded {len(customers)} customers")

    # Prepare data for clustering
    print("\n🧮 Preparing data for clustering...")

    # Test with purchase_frequency axis
    axis_name = 'purchase_frequency'

    # Extract features
    features = []
    customer_ids = []

    for customer in customers:
        # Use total_orders as the feature for purchase frequency
        if customer['total_orders'] and customer['total_orders'] > 0:
            features.append([customer['total_orders']])
            customer_ids.append(customer['customer_id'])

    features = np.array(features)

    print(f"   Features shape: {features.shape}")
    print(f"   Feature range: {features.min():.1f} to {features.max():.1f}")
    print(f"   Feature mean: {features.mean():.1f} ± {features.std():.1f}")

    # Test clustering with different k values
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    print("\n🔬 Testing cluster quality for different k values:")

    for k in [2, 3, 4, 5, 6]:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(features)

        # Calculate cluster sizes
        cluster_sizes = Counter(labels)

        # Calculate silhouette score
        silhouette = silhouette_score(features, labels)

        print(f"\n   k={k}:")
        print(f"      Silhouette score: {silhouette:.3f}")
        print(f"      Cluster sizes: {dict(sorted(cluster_sizes.items()))}")

        # Check for outlier problem
        largest_cluster = max(cluster_sizes.values())
        largest_pct = largest_cluster / len(features) * 100

        if largest_pct > 90:
            print(f"      ⚠️  WARNING: Largest cluster has {largest_pct:.1f}% of customers!")

        # Show cluster centers and ranges
        for cluster_id in range(k):
            cluster_features = features[labels == cluster_id]
            if len(cluster_features) > 0:
                print(f"      Cluster {cluster_id}: mean={cluster_features.mean():.1f}, "
                      f"range=[{cluster_features.min():.0f}, {cluster_features.max():.0f}], "
                      f"size={len(cluster_features)}")


async def main():
    """Run clustering quality tests"""
    print("\n" + "=" * 70)
    print("CLUSTERING QUALITY VALIDATION")
    print("=" * 70)
    print("\nGoal: Verify segments are descriptive and meaningful")
    print("Expected: Multiple balanced segments describing population")
    print("Problem: 'Everyone vs 3 outliers' or similar degenerate cases")

    # Get sample data
    print("\n📥 Loading customer data...")
    customers = await get_sample_customers(limit=500)
    print(f"✅ Loaded {len(customers)} customers")

    # Show basic statistics
    print("\n📊 Sample Statistics:")
    orders = [c['total_orders'] for c in customers]
    values = [c['total_value'] for c in customers]
    print(f"   Orders: {np.mean(orders):.1f} ± {np.std(orders):.1f} (range: {min(orders)}-{max(orders)})")
    print(f"   Value:  ${np.mean(values):.0f} ± ${np.std(values):.0f} (range: ${min(values):.0f}-${max(values):.0f})")

    # Test 1: Check current segment distribution
    analyze_segment_distribution(customers)

    # Test 2: Check fuzzy membership quality
    analyze_fuzzy_membership_quality(customers)

    # Test 3: Analyze segment characteristics
    analyze_segment_characteristics(customers)

    # Test 4: Test raw clustering algorithm
    await test_current_clustering_algorithm()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\nReview the analysis above to determine:")
    print("  1. Are segments balanced? (not 90% in one segment)")
    print("  2. Are segments descriptive? (clear behavioral differences)")
    print("  3. Are fuzzy memberships working? (not hard 0/1 assignments)")
    print("  4. Is k-value appropriate? (not too few, not too many)")
    print("\nIf you see warnings above, the clustering may need adjustment.")


if __name__ == "__main__":
    asyncio.run(main())
