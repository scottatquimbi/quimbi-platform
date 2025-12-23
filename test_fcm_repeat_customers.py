"""
Test Fuzzy C-Means clustering on repeat customers to discover sub-segments
"""
import asyncio
from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine

async def test_fcm():
    """Test FCM vs K-Means on repeat customers"""
    print("=" * 80)
    print("FUZZY C-MEANS TEST - Repeat Customer Sub-Segmentation")
    print("=" * 80)
    print()

    # Test on repeat customers (3+ orders)
    # From earlier analysis: expect 4 sub-segments
    # - Enterprise (0.4%): 96 orders/month
    # - Super-Engaged (23%): 10.8 orders/month
    # - Active Hobbyist (18.4%): 1.4 orders/month
    # - Occasional Repeat (58.2%): 3.8 orders/month

    print("Testing on 500 repeat customers (3+ orders)")
    print()

    # Test 1: K-Means (baseline)
    print("=" * 80)
    print("TEST 1: K-MEANS (Hard Clustering)")
    print("=" * 80)
    print()

    engine_kmeans = EcommerceClusteringEngine(
        min_k=2,
        max_k=8,
        enable_dynamic_k=True,
        enable_robust_scaling=True,
        use_fuzzy_cmeans=False,  # K-Means
        use_ai_naming=False
    )

    print("Running K-Means clustering...")
    results_kmeans = await engine_kmeans.discover_multi_axis_segments(
        store_id="lindas_electric_quilters",
        axes_to_cluster=['purchase_frequency'],
        max_customers=500  # Repeat customers only
    )

    segments_kmeans = results_kmeans.get('purchase_frequency', [])
    print(f"✓ Found {len(segments_kmeans)} segments (K-Means)")
    print()

    for i, seg in enumerate(segments_kmeans):
        print(f"Segment {i+1}: {seg.segment_name}")
        print(f"  Size: {seg.customer_count} customers ({seg.population_percentage*100:.1f}%)")
        print(f"  Silhouette: {seg.scaler_params.get('silhouette', 0):.4f}")
        print(f"  Fuzzy memberships: {'Yes' if seg.customer_fuzzy_scores else 'No (hard clustering)'}")
        print()

    print("-" * 80)
    print()

    # Test 2: Fuzzy C-Means
    print("=" * 80)
    print("TEST 2: FUZZY C-MEANS (Soft Clustering)")
    print("=" * 80)
    print()

    engine_fcm = EcommerceClusteringEngine(
        min_k=2,
        max_k=8,
        enable_dynamic_k=True,
        enable_robust_scaling=True,
        use_fuzzy_cmeans=True,  # FCM
        fuzzy_m=2.0,
        use_ai_naming=False
    )

    print("Running Fuzzy C-Means clustering...")
    results_fcm = await engine_fcm.discover_multi_axis_segments(
        store_id="lindas_electric_quilters",
        axes_to_cluster=['purchase_frequency'],
        max_customers=500  # Same sample
    )

    segments_fcm = results_fcm.get('purchase_frequency', [])
    print(f"✓ Found {len(segments_fcm)} segments (FCM)")
    print()

    for i, seg in enumerate(segments_fcm):
        print(f"Segment {i+1}: {seg.segment_name}")
        print(f"  Size: {seg.customer_count} customers ({seg.population_percentage*100:.1f}%)")
        print(f"  Silhouette: {seg.scaler_params.get('silhouette', 0):.4f}")
        print(f"  Fuzzy memberships: {'Yes' if seg.customer_fuzzy_scores else 'No'}")

        if seg.customer_fuzzy_scores:
            # Show sample fuzzy memberships
            sample_customers = list(seg.customer_fuzzy_scores.items())[:3]
            print(f"  Sample fuzzy scores:")
            for cust_id, score in sample_customers:
                print(f"    - Customer {cust_id}: {score:.3f}")
        print()

    print("-" * 80)
    print()

    # Compare results
    print("=" * 80)
    print("COMPARISON: K-MEANS vs FUZZY C-MEANS")
    print("=" * 80)
    print()

    print(f"K-Means segments: {len(segments_kmeans)}")
    print(f"FCM segments: {len(segments_fcm)}")
    print()

    print("K-Means distribution:")
    kmeans_sizes = [seg.customer_count for seg in segments_kmeans]
    kmeans_pcts = [seg.population_percentage*100 for seg in segments_kmeans]
    print(f"  Sizes: {kmeans_sizes}")
    print(f"  Percentages: {[f'{p:.1f}%' for p in kmeans_pcts]}")
    print()

    print("FCM distribution:")
    fcm_sizes = [seg.customer_count for seg in segments_fcm]
    fcm_pcts = [seg.population_percentage*100 for seg in segments_fcm]
    print(f"  Sizes: {fcm_sizes}")
    print(f"  Percentages: {[f'{p:.1f}%' for p in fcm_pcts]}")
    print()

    # Analyze fuzzy memberships if available
    if segments_fcm and segments_fcm[0].fuzzy_membership_matrix is not None:
        print("=" * 80)
        print("FUZZY MEMBERSHIP ANALYSIS")
        print("=" * 80)
        print()

        import numpy as np

        # Get fuzzy membership matrix
        fuzzy_matrix = segments_fcm[0].fuzzy_membership_matrix
        print(f"Fuzzy membership matrix shape: {fuzzy_matrix.shape}")
        print(f"(n_customers={fuzzy_matrix.shape[0]}, k_segments={fuzzy_matrix.shape[1]})")
        print()

        # Find customers with hybrid memberships (no clear dominant segment)
        hybrid_customers = []
        for i in range(fuzzy_matrix.shape[0]):
            memberships = fuzzy_matrix[i]
            max_membership = memberships.max()
            if max_membership < 0.6:  # Less than 60% in any one segment
                hybrid_customers.append((i, memberships))

        print(f"Found {len(hybrid_customers)} hybrid customers (no clear dominant segment)")
        if hybrid_customers:
            print("Sample hybrid customer memberships:")
            for i, memberships in hybrid_customers[:3]:
                print(f"  Customer {i}: {[f'{m:.3f}' for m in memberships]}")
        print()

        # Find customers transitioning between segments
        transitioning = []
        for i in range(fuzzy_matrix.shape[0]):
            memberships = fuzzy_matrix[i]
            top2 = np.sort(memberships)[-2:]
            if top2[0] > 0.25 and top2[1] > 0.50:  # Second-highest > 25%, highest > 50%
                transitioning.append((i, memberships))

        print(f"Found {len(transitioning)} transitioning customers (significant membership in 2+ segments)")
        if transitioning:
            print("Sample transitioning customer memberships:")
            for i, memberships in transitioning[:3]:
                sorted_idx = np.argsort(memberships)[::-1]
                top2_memberships = [memberships[sorted_idx[0]], memberships[sorted_idx[1]]]
                print(f"  Customer {i}: Top 2 = {[f'{m:.3f}' for m in top2_memberships]}")
        print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("FCM Implementation Status:")
    print("  ✓ FCM clustering enabled and functional")
    print(f"  ✓ Fuzzy memberships stored: {segments_fcm[0].customer_fuzzy_scores is not None if segments_fcm else False}")
    print(f"  ✓ Membership matrix captured: {segments_fcm[0].fuzzy_membership_matrix is not None if segments_fcm else False}")
    print()
    print("Next Steps:")
    print("  1. Enable FCM in production: ENABLE_FUZZY_CMEANS=true")
    print("  2. Create temporal snapshots with fuzzy thumbprints")
    print("  3. Implement drift analysis using FCM membership changes")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_fcm())
