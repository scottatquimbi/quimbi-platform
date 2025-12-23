"""
Test Hierarchical Clustering - Subdividing Broad Segments

Demonstrates automatic subdivision of segments that are too internally diverse.

Use Case: 94% "one-time buyers" segment likely contains:
- Bought yesterday (potential repeat customer)
- Bought last week (warm lead)
- Bought 6 months ago (cooling off)
- Bought 2 years ago (cold/churned)
"""
import asyncio
import numpy as np
from sqlalchemy import text
from backend.core.database import get_db_session
from backend.segmentation.hierarchical_clustering import HierarchicalClusteringEngine
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

async def test_hierarchical():
    """Test hierarchical clustering on one-time buyers"""
    print("=" * 80)
    print("HIERARCHICAL CLUSTERING TEST - Subdividing Broad Segments")
    print("=" * 80)
    print()

    # Fetch one-time buyers (1 order only)
    print("Fetching one-time buyers (1 order each)...")
    async with get_db_session() as session:
        query = text("""
            SELECT
                customer_id,
                MIN(order_date) as first_order_date,
                MAX(order_date) as last_order_date,
                SUM(line_item_sales) as total_spent,
                COUNT(DISTINCT order_id) as order_count,
                EXTRACT(EPOCH FROM (CURRENT_DATE - MAX(order_date)))/86400 as days_since_purchase
            FROM public.combined_sales
            WHERE customer_id IS NOT NULL
            GROUP BY customer_id
            HAVING COUNT(DISTINCT order_id) = 1
            ORDER BY RANDOM()
            LIMIT 1000
        """)
        result = await session.execute(query)
        customers = result.fetchall()

    print(f"✓ Found {len(customers)} one-time buyers")
    print()

    # Extract features for clustering
    print("Extracting features...")
    feature_names = [
        'days_since_purchase',
        'total_spent',
        'recency_category'  # 0-7 days, 8-30 days, 31-90 days, 91-180 days, 180+ days
    ]

    X = []
    for c in customers:
        days_since = float(c.days_since_purchase) if c.days_since_purchase else 365.0
        total_spent = float(c.total_spent) if c.total_spent else 0.0

        # Recency category
        if days_since <= 7:
            recency = 0  # Very recent (hot lead)
        elif days_since <= 30:
            recency = 1  # Recent (warm)
        elif days_since <= 90:
            recency = 2  # Medium (cooling)
        elif days_since <= 180:
            recency = 3  # Old (cold)
        else:
            recency = 4  # Very old (churned)

        X.append([days_since, total_spent, recency])

    X = np.array(X)
    print(f"Feature matrix: {X.shape}")
    print()

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Initial clustering (will likely get 1-2 segments)
    print("=" * 80)
    print("STEP 1: Initial Clustering")
    print("=" * 80)
    print()

    print("Running K-Means (k=2-6)...")
    best_k = 2
    best_sil = -1
    from sklearn.metrics import silhouette_score

    for k in range(2, 7):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels)
        if sil > best_sil:
            best_sil = sil
            best_k = k

    print(f"Best k={best_k} (silhouette={best_sil:.3f})")
    print()

    # Cluster with best k
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    print(f"Initial segments ({best_k} total):")
    for seg_id in range(best_k):
        mask = labels == seg_id
        count = mask.sum()
        pct = (count / len(customers)) * 100

        # Show characteristics of this segment
        segment_days = X[mask, 0]
        segment_spent = X[mask, 1]

        print(f"  Segment {seg_id}: {count} customers ({pct:.1f}%)")
        print(f"    Days since purchase: {segment_days.min():.0f}-{segment_days.max():.0f} (median: {np.median(segment_days):.0f})")
        print(f"    Total spent: ${segment_spent.min():.2f}-${segment_spent.max():.2f} (median: ${np.median(segment_spent):.2f})")
        print()

    # Initialize hierarchical clustering engine
    print("=" * 80)
    print("STEP 2: Hierarchical Subdivision")
    print("=" * 80)
    print()

    hierarchical_engine = HierarchicalClusteringEngine(
        max_intra_variance=2.0,         # Trigger: high variance
        max_diameter_percentile=95.0,    # Trigger: wide spread
        min_segment_size_for_split=100,  # Must have 100+ customers
        max_segment_pct=60.0,            # Trigger: segment >60%
        max_depth=2,                     # Max 2 levels of subdivision
        min_subsegment_size=30           # Subsegments must have 30+ customers
    )

    # Analyze each segment for subdivision
    all_subsegments = []

    for seg_id in range(best_k):
        mask = labels == seg_id
        center = kmeans.cluster_centers_[seg_id]

        print(f"Analyzing Segment {seg_id}...")

        # Check diversity
        diversity = hierarchical_engine.analyze_segment_diversity(
            X_scaled,
            mask,
            center,
            feature_names,
            len(customers)
        )

        print(f"  Customer count: {diversity.customer_count}")
        print(f"  Intra-cluster variance: {diversity.intra_cluster_variance:.2f}")
        print(f"  Diameter (max distance): {diversity.diameter:.2f}")
        print(f"  Needs subdivision: {diversity.needs_subdivision}")
        print(f"  Reason: {diversity.subdivision_reason}")
        print()

        if diversity.needs_subdivision:
            print(f"  🔍 Subdividing Segment {seg_id}...")

            # Define clustering function for recursive subdivision
            def recluster(X_subset):
                # Re-cluster just this segment
                k_sub = min(4, max(2, len(X_subset) // 50))  # Adaptive k
                kmeans_sub = KMeans(n_clusters=k_sub, random_state=42, n_init=10)
                return kmeans_sub.fit_predict(X_subset)

            # Recursively subdivide
            hierarchy = hierarchical_engine.recursive_cluster_segment(
                X_scaled,
                mask,
                center,
                feature_names,
                len(customers),
                recluster,
                current_depth=0,
                parent_id=f"seg_{seg_id}"
            )

            # Flatten to get leaf subsegments
            leaves = hierarchical_engine.flatten_hierarchy(hierarchy)
            all_subsegments.extend(leaves)

            print(f"  ✓ Created {len(leaves)} subsegments")
            print()
        else:
            # Keep as-is
            all_subsegments.append({
                'segment_id': f"seg_{seg_id}",
                'depth': 0,
                'customer_count': diversity.customer_count,
                'diversity': diversity,
                'is_leaf': True,
                'subsegments': None
            })

    # Final results
    print("=" * 80)
    print("FINAL HIERARCHICAL SEGMENTS")
    print("=" * 80)
    print()

    print(f"Total subsegments after hierarchical clustering: {len(all_subsegments)}")
    print()

    for subseg in sorted(all_subsegments, key=lambda x: x['customer_count'], reverse=True):
        count = subseg['customer_count']
        pct = (count / len(customers)) * 100
        depth = subseg['depth']
        seg_id = subseg['segment_id']

        indent = "  " * depth
        print(f"{indent}Subsegment {seg_id}: {count} customers ({pct:.1f}%) [depth={depth}]")

    print()
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()

    print("WITHOUT Hierarchical Clustering:")
    print(f"  - {best_k} segments")
    for seg_id in range(best_k):
        mask = labels == seg_id
        count = mask.sum()
        pct = (count / len(customers)) * 100
        print(f"    Segment {seg_id}: {pct:.1f}%")

    print()
    print("WITH Hierarchical Clustering:")
    print(f"  - {len(all_subsegments)} subsegments (after recursive subdivision)")
    for subseg in sorted(all_subsegments, key=lambda x: x['customer_count'], reverse=True):
        count = subseg['customer_count']
        pct = (count / len(customers)) * 100
        print(f"    {subseg['segment_id']}: {pct:.1f}%")

    print()
    print("=" * 80)
    print("BUSINESS VALUE")
    print("=" * 80)
    print()
    print("Hierarchical clustering reveals hidden sub-groups within broad segments:")
    print()
    print("Example: 'One-time buyers' (94%) subdivided into:")
    print("  - Bought 0-7 days ago (hot leads - send immediate follow-up)")
    print("  - Bought 8-30 days ago (warm - send reminder email)")
    print("  - Bought 31-90 days ago (cooling - win-back campaign)")
    print("  - Bought 91-180 days ago (cold - discount offer)")
    print("  - Bought 180+ days ago (churned - remove from active marketing)")
    print()
    print("Each subsegment gets tailored campaigns instead of generic 'one-time buyer' treatment")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_hierarchical())
